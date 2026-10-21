# SameBoy 无头捕获

原工作区用 BGB 的命令行驱动截图：

```
bgb64.exe -rom R -state IN.sna -demoplay IN.dem \
          -br 'ADDR/ROMBANK=N' -stateonexit OUT.sna -screenonexit OUT.png
```

BGB 是 Windows 程序，本机没有 wine。SameBoy 是 MIT 许可、可在 Linux 原生构建，
但它的 SDL 前端只接受 `[--fullscreen] [rom]`，没有状态装载、断点或按键脚本。
`00_Tools/sameboy_capture.c` 直接链接 SameBoy 的 `Core/`，把上面那套能力补齐。

## 构建

```bash
git clone --branch bess https://github.com/LIJI32/SameBoy.git /tmp/sb
cd /tmp/sb
# rgbds 必须在 PATH 上；SDL 前端与 Core 共用一份源码
CONF=release make -j4 sdl

gcc -O2 -DGB_INTERNAL -I. -o /tmp/sameboy_capture \
    "$REPO/00_Tools/sameboy_capture.c" Core/*.c \
    $(pkg-config --cflags --libs libpng) -lm
```

## 启动 ROM（必需）

SameBoy **不带内置启动 ROM**。缺了它 CPU 会停在启动区，LCD 不打开，
`GB_run_frame` 永远等不到 VBlank，结果是一张全白图（`LCDC=00 vram_nz=0`）。
在 `GB_load_rom` 之后设置 `boot_rom_finished` 也不管用：PC 仍从 `$0000` 起跑。

用 SameBoy 自己那份开源替代启动 ROM（由 `BootROMs/dmg_boot.asm` 汇编，256 字节，
不是任天堂原版）：

| 项 | 值 |
| --- | --- |
| 大小 | 256 字节 |
| md5 | `6344d08bbbcbedbbaef9ddbdf7632c74` |
| sha1 | `1db57a1e8b6e4096f811587f9eab0c6675fd9755` |
| sha256 | `6f64da4cecd7e54e2f928eb3e3ba7810a7a567d0d247cc71737d1771e073a916` |

仓库不分发该文件。`--boot` 指向本地副本即可。

## 用法

```bash
# 冷启动跑 200 帧后截图
/tmp/sameboy_capture --rom ROM.gb --boot dmg_boot.bin --frames 200 --shot out.png

# 按 START 进入结局序列，跑到第 7200 帧
/tmp/sameboy_capture --rom ROM.gb --boot dmg_boot.bin \
    --keys 240:start --keys-hold 12 --frames 7200 --shot out.png

# 装载状态、在断点处导出状态
/tmp/sameboy_capture --rom ROM.gb --boot dmg_boot.bin \
    --state in.sna --frames 600 --breakpoint 4b48 --save-state out.sna --shot out.png
```

| 参数 | 对应 BGB | 说明 |
| --- | --- | --- |
| `--state` | `-state` | 载入 BESS 存档 |
| `--save-state` | `-stateonexit` | 退出时导出状态 |
| `--frames` | `-demoplay` | 跑多少帧 |
| `--shot` | `-screenonexit` | 截图路径 |
| `--breakpoint` | `-br` | PC 断点，命中后提前结束（退出码 2） |
| `--keys` | `.dem` | 按键脚本，如 `240:start`、`300:a+start` |
| `--boot` | （BGB 内置） | 启动 ROM |

## 与 BGB 存档互通

BGB 的 `.sna` 就是 **BESS** 文件（规范见 SameBoy 仓库的 `BESS.md`），
SameBoy 的 Core 既读也写这个格式，所以两边的状态可以直接互相装载，无需转换。
`00_Tools/bgb_state.py` 是不依赖模拟器的纯 Python BESS 解析器，用于在脚本里
直接读 VRAM/WRAM/IO。

CORE 块关键偏移（`0x8800` 项目里踩过坑：`0x98` 是 RAM 大小，VRAM 指针在 `0xA4`）：

| 偏移 | 含义 |
| --- | --- |
| `0x04` | 4 字符机型（如 `GD  `） |
| `0x08` / `0x0A` / `0x12` | PC / AF / SP |
| `0x18` | 128 字节 IO 寄存器（LCDC 在 `+0x58`） |
| `0x98` / `0x9C` | WRAM 大小 / 偏移 |
| `0xA0` / `0xA4` | VRAM 大小 / 偏移 |
| `0xB0` / `0xB4` | OAM 大小 / 偏移 |
| `0xB8` / `0xBC` | HRAM 大小 / 偏移 |

## 用它验证了什么

v0.5.4 的通关提示页精灵修复就是用这套驱动验证的：

- 载入旧版捕获包的 `.sna`，SameBoy 直接渲染出正确的图鉴页，
  `vram_nz` 与 BESS 解析结果一致，证明状态真正生效。
- 复现了精灵乱码，并确认日版原版在同一位置显示完整角色 —— 排除模拟器差异。
- 逐帧导出动画窗口，配合 `pixel_delta` / `vram_diff` / `anim_mask` 判定：
  动画期间 **VRAM 图块一个字节都没改**，只有 OAM 在变，说明问题不是「动画缺图块」，
  而是提示页图块集装载时**覆盖了精灵要用的槽位**。
- 修复后：页面渲染逐像素一致，精灵保留集在 VRAM 中与日版逐字节一致。

## 注意

- `--boot` 与 `.sna` 都不入库（见 `00_Tools/audit_public_tree.py`）。
- SameBoy 的 `BootROMs/*.asm` 需要 rgbds 汇编；本机 rgbds 1.0.4 的语法与
  旧脚本不兼容，因此这里直接用现成的 256 字节启动 ROM，而不是现场汇编。

## GUI 取帧（真实滤镜渲染，推荐）

上面这套无头驱动只能拿到 Core 的 160×144 原始缓冲。`Monochrome LCD Display`
这类滤镜是 SDL 前端的 GLSL 着色器（`Shaders/MonoLCD.fsh` 经 `MasterShader.fsh` 拼接），
外面还套着帧混合（`previous_image`）、`origin`/`output_resolution` 变换和 sRGB 处理，
**无法**在 CPU 上复刻——曾经照抄那 40 行数学做过一版移植，和真实输出明显不一致，已弃用。

正确做法是给 SDL 前端打补丁，让它自己渲染、自己抓帧：

- 补丁：`00_Tools/sameboy_gui_capture.patch`
- 新增 `--keys`（内部按键脚本，不用 xdotool）、`--frames`、`--record`、`--record-from`
- 渲染到离屏 FBO 再 `glReadPixels`，不调用 `SDL_GL_SwapWindow`
- 默认 `MonoLCD` + `Lime (Game Boy)` 调色板 + 6× 缩放 + ACCURATE 帧混合

两个关键坑：

1. 必须用 `GB_run_frame` 而不是 `GB_run`。后者跑到「下一次 vblank」就返回，而启动 ROM
   阶段 LCD 未开、永远没有 vblank，会导致每次只执行一条指令，PC 在 `$0000-$000A` 空转。
2. 必须离屏渲染。Xvfb + Mesa 软件渲染没有 DRI3，`SDL_GL_SwapWindow` 会卡死在 `poll()`。

运行方式与产物说明见 `build/review_sameboy/README.md`。
