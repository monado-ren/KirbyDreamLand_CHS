#!/usr/bin/env python3
"""Render the whole visual-review video set with SameBoy.

Pipeline
--------
1. Build the patched ROM copies the fixtures need (stage 1-5, GAME OVER,
   hint pages, ending) from the localised ROM.
2. Run SameBoy's SDL frontend once per run, recording raw frames through a FIFO
   into ffmpeg and the APU samples into a WAV, then mux them together.
3. Concatenate the runs in story order.
4. Composite the result onto ``build/review_sameboy/bg.png`` at its native
   resolution, centred, with a pure black shadow (0 deg, 0 distance, 50 blur).

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


def record(name, rom, start, end, keys, args, out_dir):
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
    encode = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
              "-pix_fmt", "rgb24", "-s", "960x864", "-r", FPS, "-i", "-",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-pix_fmt", "yuv420p", str(vid)]

    proc = subprocess.Popen(capture, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, env=env,
                            cwd=str(Path(args.sameboy).parent))
    src = open(fifo, "rb")
    ff = subprocess.Popen(encode, stdin=src)
    src.close()
    ff.wait()
    proc.wait()
    fifo.unlink()

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid),
                    "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "128k", "-shortest", str(mp4)], check=True)
    vid.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    return mp4


def concat(paths, out_path):
    listing = Path("/tmp/review_concat.txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in paths), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)],
                   check=True)


def build_background(bg_path, video_size, blur, out_path):
    """bg.png with a pure black, zero-offset shadow behind the video rectangle."""
    bg = Image.open(bg_path).convert("RGBA")
    width, height = bg.size
    vw, vh = video_size
    x, y = (width - vw) // 2, (height - vh) // 2
    shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([x, y, x + vw - 1, y + vh - 1],
                                     fill=(0, 0, 0, 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    Image.alpha_composite(bg, shadow).convert("RGB").save(out_path)
    return x, y


def composite(bg_path, video, out_path, blur):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                            "-show_entries", "stream=width,height", "-of",
                            "csv=p=0:s=x", str(video)],
                           capture_output=True, text=True, check=True)
    vw, vh = (int(v) for v in probe.stdout.strip().split("x"))
    bg_file = Path("/tmp/review_bg_shadow.png")
    x, y = build_background(bg_path, (vw, vh), blur, bg_file)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(bg_file),
         "-i", str(video), "-filter_complex",
         f"[0:v][1:v]overlay={x}:{y}:shortest=1,format=yuv420p[v]",
         "-map", "[v]", "-map", "1:a", "-r", FPS, "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "20", "-c:a", "copy",
         "-movflags", "+faststart", str(out_path)],
        check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sameboy", default="/tmp/sb_run/sameboy")
    parser.add_argument("--boot", default="/tmp/dmg_boot.bin")
    parser.add_argument("--rom", default="KirbyDreamLand_CHS-Monado.gb")
    parser.add_argument("--out", default="build/review_sameboy")
    parser.add_argument("--rom-dir", default="/tmp/sb_roms")
    parser.add_argument("--bg", default="build/review_sameboy/bg.png")
    parser.add_argument("--shadow-blur", type=float, default=50.0)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--skip-composite", action="store_true")
    args = parser.parse_args()
    # The emulator runs with cwd next to its own binary, so every path handed to
    # it (and to ffmpeg) has to be absolute.
    args.rom = str(Path(args.rom).resolve())
    args.boot = str(Path(args.boot).resolve())
    args.sameboy = str(Path(args.sameboy).resolve())
    args.bg = str(Path(args.bg).resolve())

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    roms = build_fixture_roms(Path(args.rom).read_bytes(), Path(args.rom_dir))
    roms["base"] = Path(args.rom).resolve()

    produced = {}
    for name, rom_key, start, end, keys in RUNS:
        if args.only and not any(o in name for o in args.only):
            continue
        print(f"{name}: {start}..{end - 1}", flush=True)
        produced[name] = record(name, roms[rom_key], start, end, keys, args, out_dir)

    combined = out_dir / "ALL_COMBINED.mp4"
    order = [n for n in COMBINED_ORDER if (out_dir / f"{n}.mp4").exists()]
    if len(order) == len(COMBINED_ORDER):
        concat([out_dir / f"{n}.mp4" for n in order], combined)
        print(f"concat: {len(order)} segments -> {combined}", flush=True)
        if not args.skip_composite:
            final = out_dir / "ALL_COMBINED_BG.mp4"
            composite(Path(args.bg), combined, final, args.shadow_blur)
            print(f"composite: {final}", flush=True)


if __name__ == "__main__":
    main()
