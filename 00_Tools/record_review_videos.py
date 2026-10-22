#!/usr/bin/env python3
"""Render the whole visual-review video set with SameBoy.

Pipeline
--------
1. Build the patched ROM copies the fixtures need (stage 1-5, GAME OVER,
   hint pages, ending) from the localised ROM.
2. Run SameBoy's SDL frontend once per run, recording raw frames through a FIFO
   into ffmpeg and the APU samples into a WAV, then mux them together.
3. Concatenate the runs in story order.
4. Composite each segment onto its release artwork from ``03_Image/release``
   (the game area is the centred 960x864 window) inside the same encode, so the
   picture is compressed exactly once.
5. Prefix the first segment with a 2 s hold of ``kirby_chs_release.png`` that
   cross-fades into run 01, and delay that segment's audio by 2 s to match,
   then concatenate the segments without re-encoding.

The DMG picture is compressed exactly once: SameBoy hands out raw RGB24, the
background is composited losslessly in the same filter graph, and every step
after the libx264 pass (mux, concat) is ``-c copy``.

The frontend must be the patched one from ``00_Tools/sameboy_gui_capture.patch``
(``--keys`` / ``--frames`` / ``--record`` / ``--record-from`` / ``--audio``).

Usage
-----
    python3 00_Tools/record_review_videos.py \
        --sameboy /tmp/sb_run/sameboy \
        --boot /tmp/dmg_boot.bin \
        --rom KirbyDreamLand_CHS-Monado.gb \
        [--only 04_ 08_] [--skip-composite]
"""
import argparse
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

FPS = "4194304/70224"          # Game Boy frame rate, 59.7275 Hz
SAMPLE_RATE = 48000
EXTRA = 600                    # default: 10 more seconds after the original end
EXTRA_BY_NAME = {"01_title_menu_config_sound": 180}

# name, rom key, start frame, end frame, key script
#   end frame is exclusive; the recording covers [start, end)
RUNS = [
    ("01_title_menu_config_sound", "base", 0, 1280,
     "742:p:up+select+a,746:r:up+select+a,817:p:down+select+b,821:r:down+select+b,"
     "912:p:down,914:r:down,944:p:down,946:r:down,976:p:a,978:r:a"),
    ("02_hud_normal", "base", 232, 1319, "232:p:start,242:r:start"),
    ("03_hud_extra", "base", 232, 1351,
     "232:p:up+select+a,236:r:up+select+a,267:p:start,277:r:start"),
    ("04_stage_1_intro", "stage_1", 272, 810, "232:p:start,242:r:start"),
    ("05_stage_2_intro", "stage_2", 272, 829, "232:p:start,242:r:start"),
    ("06_stage_3_intro", "stage_3", 272, 890, "232:p:start,242:r:start"),
    ("07_stage_4_intro", "stage_4", 272, 881, "232:p:start,242:r:start"),
    ("08_stage_5_intro", "stage_5", 272, 1733, "232:p:start,242:r:start"),
    ("09_game_over_continue", "gameover", 254, 851, "232:p:start,242:r:start"),
    ("10_hint_normal", "hint_normal", 6060, 8386, "232:p:start,244:r:start"),
    ("11_hint_extra", "hint_extra", 6929, 16123, "232:p:start,244:r:start"),
    ("12_ending_extra", "ending_extra", 232, 13984, "232:p:start,242:r:start"),
]
# 每段用的发布版背景（03_Image/release/），游戏区固定为居中的 960x864
RELEASE_BG = {
    "01_title_menu_config_sound": "01标题界面 & 配置模式.png",
    "04_stage_1_intro": "04-08各场景 开场动画.png",
    "05_stage_2_intro": "04-08各场景 开场动画.png",
    "06_stage_3_intro": "04-08各场景 开场动画.png",
    "07_stage_4_intro": "04-08各场景 开场动画.png",
    "08_stage_5_intro": "04-08各场景 开场动画.png",
    "09_game_over_continue": "09游戏结束.png",
    "10_hint_normal": "10剧终 额外模式提示.png",
    "11_hint_extra": "11敌人图鉴 配置模式提示.png",
}
RELEASE_CARD = "kirby_chs_release.png"
GAME_ORIGIN = (480, 108)      # 背景上游戏窗口的位置（960x864）
INTRO_SECONDS = 2.0           # 发布图静止展示时长
FADE_SECONDS = 0.5            # 淡入第一段

COMBINED_ORDER = [
    "01_title_menu_config_sound", "04_stage_1_intro", "05_stage_2_intro",
    "06_stage_3_intro", "07_stage_4_intro", "08_stage_5_intro",
    "09_game_over_continue", "10_hint_normal", "11_hint_extra",
]


def build_fixture_roms(rom_bytes, out_dir):
    """Patch $40E4 and 0x1809C in copies of the ROM, like the capture fixtures."""
    out_dir.mkdir(parents=True, exist_ok=True)
    f = lambda addr, bank=6: bank * 0x4000 + (addr - 0x4000)
    roms = {}

    for stage in range(5):
        data = bytearray(rom_bytes)
        assert data[f(0x40E4):f(0x40E6)] == bytes.fromhex("3eff"), "stage site moved"
        data[f(0x40E4):f(0x40E7)] = bytes.fromhex("c36067")      # jp $6760
        stub = (bytes.fromhex("3eff" "ea96d0") + bytes([0x3E, stage])
                + bytes.fromhex("ea3bd0" "c3e940"))
        data[f(0x6760):f(0x6760) + len(stub)] = stub
        path = out_dir / f"stage_{stage + 1}.gb"
        path.write_bytes(bytes(data))
        roms[f"stage_{stage + 1}"] = path

    data = bytearray(rom_bytes)
    data[0x180E4:0x180E7] = bytes.fromhex("c35747")                   # GAME OVER
    (out_dir / "gameover.gb").write_bytes(bytes(data))
    roms["gameover"] = out_dir / "gameover.gb"

    for key, rep in (("hint_normal", "c36c48"), ("hint_extra", "c3d440"),
                     ("ending_extra", "c3d440")):
        data = bytearray(rom_bytes)
        assert data[0x1809C:0x1809F] == bytes.fromhex("cd961e"), "hint site moved"
        data[0x1809C:0x1809F] = bytes.fromhex(rep)
        (out_dir / f"{key}.gb").write_bytes(bytes(data))
        roms[key] = out_dir / f"{key}.gb"
    return roms


def record(name, rom, start, end, keys, args, out_dir, bg_path=None, card=None):
    mp4 = out_dir / f"{name}.mp4"
    vid = out_dir / f"{name}.video.mp4"
    wav = Path(f"/tmp/{name}.wav")
    fifo = Path(f"/tmp/{name}.fifo")
    if fifo.exists():
        fifo.unlink()
    os.mkfifo(fifo)

    env = dict(os.environ, SDL_VIDEODRIVER="offscreen", SDL_AUDIODRIVER="dummy")
    capture = [args.sameboy, "--frames", str(end), "--record", str(fifo),
               "--record-from", str(start), "--keys", keys,
               "--audio", str(wav), str(rom)]

    x, y = GAME_ORIGIN
    inputs, graph, audio_delay = [], [], 0
    if card:
        # 片头：发布图静止 2 秒，再用 0.5 秒淡入第一段
        inputs += ["-loop", "1", "-framerate", FPS, "-t",
                   str(INTRO_SECONDS + FADE_SECONDS), "-i", str(card)]
    inputs += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "960x864",
               "-r", FPS, "-i", "-"]
    if bg_path:
        inputs += ["-loop", "1", "-framerate", FPS, "-i", str(bg_path)]

    # 输入顺序：有片头时 [0]=发布图 [1]=原始帧 [2]=背景；没有片头时 [0]=原始帧 [1]=背景
    game_idx = 1 if card else 0
    if bg_path:
        bg_idx = game_idx + 1
        graph.append(f"[{bg_idx}:v]format=rgb24[bg]")
        graph.append(f"[bg][{game_idx}:v]overlay={x}:{y}:shortest=1,"
                     f"setsar=1,format=rgb24[game]")
    else:
        graph.append(f"[{game_idx}:v]setsar=1,format=rgb24[game]")
    if card:
        graph.append("[0:v]format=rgb24,fps=" + FPS + ",setsar=1[card]")
        graph.append("[card][game]xfade=transition=fade:duration="
                     + str(FADE_SECONDS) + ":offset=" + str(INTRO_SECONDS)
                     + "[x]")
        graph.append("[x]format=yuv420p[v]")
        # xfade 从 offset 就开始叠化，游戏第 0 帧出现在 offset 处，
        # 所以音轨只延后 INTRO_SECONDS，不含淡入时长。
        audio_delay = int(round(INTRO_SECONDS * 1000))
    else:
        graph.append("[game]format=yuv420p[v]")

    encode = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
              "-filter_complex", ";".join(graph), "-map", "[v]",
              "-r", FPS, "-c:v", "libx264", "-preset", "veryfast",
              "-crf", "18", "-pix_fmt", "yuv420p", str(vid)]

    proc = subprocess.Popen(capture, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, env=env,
                            cwd=str(Path(args.sameboy).parent))
    src = open(fifo, "rb")
    ff = subprocess.Popen(encode, stdin=src)
    src.close()
    ff.wait()
    proc.wait()
    fifo.unlink()

    mux = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid),
           "-i", str(wav), "-c:v", "copy"]
    # apad + -shortest: pad the audio with silence instead of letting
    # -shortest chop the last few video frames off when the capture is a
    # fraction of a frame shorter than the picture.
    if audio_delay:
        # 片头没有声音，第一段的音轨要整体后移
        mux += ["-af", f"adelay={audio_delay}|{audio_delay},apad", "-c:a", "aac"]
    else:
        mux += ["-af", "apad", "-c:a", "aac"]
    mux += ["-b:a", "128k", "-shortest", str(mp4)]
    subprocess.run(mux, check=True)
    vid.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    return mp4


def concat(paths, out_path):
    listing = Path("/tmp/review_concat.txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in paths), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)],
                   check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sameboy", default="/tmp/sb_run/sameboy")
    parser.add_argument("--boot", default="/tmp/dmg_boot.bin")
    parser.add_argument("--rom", default="KirbyDreamLand_CHS-Monado.gb")
    parser.add_argument("--out", default="build/review_sameboy")
    parser.add_argument("--rom-dir", default="/tmp/sb_roms")
    parser.add_argument("--release-dir", default="03_Image/release")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--all-segments", action="store_true",
                        help="also record 02/03/12, which are not part of the "
                             "concatenated release video")
    args = parser.parse_args()
    # The emulator runs with cwd next to its own binary, so every path handed to
    # it (and to ffmpeg) has to be absolute.
    args.rom = str(Path(args.rom).resolve())
    args.boot = str(Path(args.boot).resolve())
    args.sameboy = str(Path(args.sameboy).resolve())
    args.release_dir = str(Path(args.release_dir).resolve())

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    roms = build_fixture_roms(Path(args.rom).read_bytes(), Path(args.rom_dir))
    roms["base"] = Path(args.rom).resolve()

    release_dir = Path(args.release_dir)
    card = (release_dir / RELEASE_CARD).resolve() if RELEASE_CARD else None
    if card and not card.exists():
        card = None

    produced = {}
    for name, rom_key, start, end, keys in RUNS:
        if args.only and not any(o in name for o in args.only):
            continue
        if not args.all_segments and name not in RELEASE_BG:
            continue
        print(f"{name}: {start}..{end - 1}", flush=True)
        bg = (release_dir / RELEASE_BG[name]).resolve() if name in RELEASE_BG else None
        head = card if (card and name == COMBINED_ORDER[0]) else None
        produced[name] = record(name, roms[rom_key], start, end, keys, args,
                                out_dir, bg, head)

    order = [n for n in COMBINED_ORDER if (out_dir / f"{n}.mp4").exists()]
    if len(order) == len(COMBINED_ORDER):
        final = out_dir / "ALL_COMBINED_RELEASE.mp4"
        concat([out_dir / f"{n}.mp4" for n in order], final)
        print(f"concat (no re-encode): {len(order)} segments -> {final}",
              flush=True)


if __name__ == "__main__":
    main()
