# 工序与修改内容（细粒度）

由 `python 00_Tools/change_surface.py report --write` 生成；补丁由符号层派生并核对，
不要手改本文件。总览见 `CHANGE_SURFACE_COMPOSITION.md`。

## 00 操作工序（从素材到发布）

| # | 动作 | 命令/工具 | 输入 | 输出 | 校验 |
| ---: | --- | --- | --- | --- | --- |
| 1 | 改译文 | 编辑 `02_Text/zh-Hans.json` | 审稿文本 | 译文条目 | `text_layout.py check` 前会显示差异 |
| 2 | 重排文本页 | `00_Tools/text_layout.py render --write` | `02_Text/layout.json` + 字体 + 译文 + `03_Image/text-base/` | `03_Image/pages/<page>.png` | `text_layout.py check` |
| 3 | 改整页图 | 编辑 `03_Image/pages/*.png` | 页面 PNG | 页面 PNG | `pages.py render --check` |
| 4 | 回写图块/地图 | `00_Tools/pages.py retile <page>.png` | 页面 PNG | `03_Image/graphics/*.png` | `pages.py render --check` |
| 5 | 改覆盖层页 | 编辑 `build/pages/<page>.png` 后 `page_edits.py extract` | 基线+覆盖层 | `03_Image/edits/*` | `page_edits.py check` |
| 6 | 刷清单 | `00_Tools/repack.py --version vX.Y.Z` | `03_Image/graphics` | `04_Data/manifest.json` | `verify.py` |
| 7 | 改补丁语义 | 编辑 `06_ProgramFix/change_surface.json` / `patches/*.asm` | 符号层 | 派生补丁 | `change_surface.py check --base baserom.gb` |
| 8 | 同步摘要 | `change_surface.py sync-manifest --write` | 派生补丁 | manifest `change_surface.sha256` | `change_surface.py check` |
| 9 | 构建 | `00_Tools/build.py` | `baserom.gb` + manifest + 资源 | `KirbyDreamLand_CHS-Monado.gb` | `verify.py` |
| 10 | 发布 | `00_Tools/release.py` | 构建 ROM + `baserom.gb` | `patches/*.xdelta3` | `SHA256SUMS.txt` |

## 01 容器扩容

把 256 KiB 卡带扩成 512 KiB，并让头部声明正确。

| 偏移 | kind | 旧 → 新 | 说明 |
| --- | --- | --- | --- |
| `0x00148` | `rom.size` | `3` → `4` | 256 KiB→512 KiB，MBC1 size code 3→4 |

## 02 代码区域

唯一改游戏逻辑的补丁：VBlank 里“每帧写一行 BG map”改成“每帧写两行”。

| 偏移 | site | kind | 字节 | 资源 | 旧 → 新 | 说明 |
| --- | --- | --- | ---: | --- | --- | --- |
| `0x180A6` | `two_row_vblank_queue_writer` | `code.region` | 1 | `-` | `0x45` → `0x47` | 循环长度 10→12 |
| `0x180A8` | `two_row_vblank_queue_writer` | `code.region` | 10 | `-` | `0x11ca402100cb3e0af578` → `0x2100cb16d41e0c782279` | 改为从 0xD40C 暂存区取 12 个条目，队列基址 0xCB00，行宽 20，跳过 12 列 |
| `0x180B3` | `two_row_vblank_queue_writer` | `code.region` | 1 | `-` | `0x79` → `0x7a` | 循环计数/条件分支调整 |
| `0x180B5` | `two_row_vblank_queue_writer` | `code.region` | 20 | `-` | `0x1a221303f13d20f3afea1ecbfa91ffcbd7ea91ff` → `0x140c7bfe0720020e671d20eeaf77f091cbd7e091` | 两行/帧写入循环（含 0x67 回绕） |

## 03 图块/整包装载器

把 HUD、开场装饰、结局精灵、整包页、图鉴页的装载源改到扩展 bank 的新资源。

| 偏移 | site | kind | 字节 | 资源 | 旧 → 新 | 说明 |
| --- | --- | --- | ---: | --- | --- | --- |
| `0x01B44` | `normal_hud_load` | `loader.source_addr` | 2 | `rom_041000` | `0x4855` → `rom_041000.cpu_address=0x5000` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x01B4A` | `normal_hud_load` | `loader.bank` | 1 | `rom_041000` | `0x02` → `rom_041000.bank=0x10` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x01B5C` | `extra_hud_load` | `loader.source_addr` | 2 | `rom_041103` | `0x4866` → `rom_041103.cpu_address=0x5103` | 额外 HUD 图块装载点（重复 2 处） |
| `0x01B62` | `extra_hud_load` | `loader.bank` | 1 | `rom_041103` | `0x0A` → `rom_041103.bank=0x10` | 额外 HUD 图块装载点（重复 2 处） |
| `0x1804E` | `title_bundle_load` | `loader.vram_base` | 1 | `rom_070000` | `0x98` → `0x88` | 标题整包装载：源 bank 3→28，VRAM 目的 0x9800→0x8800 |
| `0x18050` | `title_bundle_load` | `loader.bank` | 1 | `rom_070000` | `0x03` → `rom_070000.bank=0x1C` | 标题整包装载：源 bank 3→28，VRAM 目的 0x9800→0x8800 |
| `0x18297` | `normal_hud_load` | `loader.source_addr` | 2 | `rom_041000` | `0x4855` → `rom_041000.cpu_address=0x5000` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x1829D` | `normal_hud_load` | `loader.bank` | 1 | `rom_041000` | `0x02` → `rom_041000.bank=0x10` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x182AF` | `extra_hud_load` | `loader.source_addr` | 2 | `rom_041103` | `0x4866` → `rom_041103.cpu_address=0x5103` | 额外 HUD 图块装载点（重复 2 处） |
| `0x182B5` | `extra_hud_load` | `loader.bank` | 1 | `rom_041103` | `0x0A` → `rom_041103.bank=0x10` | 额外 HUD 图块装载点（重复 2 处） |
| `0x18311` | `normal_hud_load` | `loader.source_addr` | 2 | `rom_041000` | `0x4855` → `rom_041000.cpu_address=0x5000` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x18317` | `normal_hud_load` | `loader.bank` | 1 | `rom_041000` | `0x02` → `rom_041000.bank=0x10` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x18351` | `intro_decoration_load` | `loader.source_addr` | 2 | `rom_058000` | `0x5CAD` → `rom_058000.cpu_address=0x4000` | 开场装饰图块装载点（重复 2 处） |
| `0x18357` | `intro_decoration_load` | `loader.bank` | 1 | `rom_058000` | `0x03` → `rom_058000.bank=0x16` | 开场装饰图块装载点（重复 2 处） |
| `0x18766` | `gameover_map_load` | `loader.source_addr` | 2 | `rom_04454c` | `0x4616` → `rom_04454c.cpu_address=0x454C` | GAME OVER 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x1876A` | `gameover_map_load` | `loader.vram_base` | 1 | `rom_04454c` | `0x98` → `0x90` | GAME OVER 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x1876C` | `gameover_map_load` | `loader.bank` | 1 | `rom_04454c` | `0x03` → `rom_04454c.bank=0x11` | GAME OVER 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x187E1` | `intro_decoration_load` | `loader.source_addr` | 2 | `rom_058000` | `0x5CAD` → `rom_058000.cpu_address=0x4000` | 开场装饰图块装载点（重复 2 处） |
| `0x187E7` | `intro_decoration_load` | `loader.bank` | 1 | `rom_058000` | `0x03` → `rom_058000.bank=0x16` | 开场装饰图块装载点（重复 2 处） |
| `0x187EC` | `continue_map_load` | `loader.source_addr` | 2 | `rom_044734` | `0x4666` → `rom_044734.cpu_address=0x4734` | CONTINUE 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x187F0` | `continue_map_load` | `loader.vram_base` | 1 | `rom_044734` | `0x98` → `0x90` | CONTINUE 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x187F2` | `continue_map_load` | `loader.bank` | 1 | `rom_044734` | `0x03` → `rom_044734.bank=0x11` | CONTINUE 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x188B2` | `ending_sprites_load` | `loader.source_addr` | 2 | `rom_050000` | `0x4F80` → `rom_050000.cpu_address=0x4000` | 结局精灵表装载点（重复 2 处） |
| `0x188B8` | `ending_sprites_load` | `loader.bank` | 1 | `rom_050000` | `0x03` → `rom_050000.bank=0x14` | 结局精灵表装载点（重复 2 处） |
| `0x1890A` | `normal_hud_load` | `loader.source_addr` | 2 | `rom_041000` | `0x4855` → `rom_041000.cpu_address=0x5000` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x18910` | `normal_hud_load` | `loader.bank` | 1 | `rom_041000` | `0x02` → `rom_041000.bank=0x10` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x18989` | `ending_sprites_load` | `loader.source_addr` | 2 | `rom_050000` | `0x4F80` → `rom_050000.cpu_address=0x4000` | 结局精灵表装载点（重复 2 处） |
| `0x1898F` | `ending_sprites_load` | `loader.bank` | 1 | `rom_050000` | `0x03` → `rom_050000.bank=0x14` | 结局精灵表装载点（重复 2 处） |
| `0x18D36` | `ending_034000_load` | `loader.bank` | 1 | `rom_048000` | `0x0D` → `rom_048000.bank=0x12` | 图鉴页装载点（bank）：图鉴页·黑刺球等 + 蘑菇林 图块集 |
| `0x18D3B` | `ending_0345c0_load` | `loader.source_addr` | 2 | `rom_048462` | `0x45C0` → `rom_048462.cpu_address=0x4462` | 图鉴页装载点（bank）：图鉴页·黑刺球等 + 蘑菇林 地图 |
| `0x18D41` | `ending_0345c0_load` | `loader.bank` | 1 | `rom_048462` | `0x0D` → `rom_048462.bank=0x12` | 图鉴页装载点（bank）：图鉴页·黑刺球等 + 蘑菇林 地图 |
| `0x18D60` | `ending_0346fb_load` | `loader.source_addr` | 2 | `rom_04c000` | `0x46FB` → `rom_04c000.cpu_address=0x4000` | 图鉴页装载点（bank）：图鉴页·喳喳鸟等 + 山丘 图块集 |
| `0x18D66` | `ending_0346fb_load` | `loader.bank` | 1 | `rom_04c000` | `0x0D` → `rom_04c000.bank=0x13` | 图鉴页装载点（bank）：图鉴页·喳喳鸟等 + 山丘 图块集 |
| `0x18D6B` | `ending_034cb4_load` | `loader.source_addr` | 2 | `rom_04c4f4` | `0x4CB4` → `rom_04c4f4.cpu_address=0x44F4` | 图鉴页装载点（bank）：图鉴页·喳喳鸟等 + 山丘 地图 |
| `0x18D71` | `ending_034cb4_load` | `loader.bank` | 1 | `rom_04c4f4` | `0x0D` → `rom_04c4f4.bank=0x13` | 图鉴页装载点（bank）：图鉴页·喳喳鸟等 + 山丘 地图 |
| `0x18D90` | `ending_034dc0_load` | `loader.source_addr` | 2 | `rom_074000` | `0x4DC0` → `rom_074000.cpu_address=0x4000` | 图鉴页装载点（bank）：图鉴第 3 页·大波比兄弟/风语大树 图块集 |
| `0x18D96` | `ending_034dc0_load` | `loader.bank` | 1 | `rom_074000` | `0x0D` → `rom_074000.bank=0x1D` | 图鉴页装载点（bank）：图鉴第 3 页·大波比兄弟/风语大树 图块集 |
| `0x18D9B` | `ending_03535c_load` | `loader.source_addr` | 2 | `rom_0742b3` | `0x535C` → `rom_0742b3.cpu_address=0x42B3` | 图鉴页装载点（bank）：图鉴第 3 页·大波比兄弟/风语大树 地图 |
| `0x18DA1` | `ending_03535c_load` | `loader.bank` | 1 | `rom_0742b3` | `0x0D` → `rom_0742b3.bank=0x1D` | 图鉴页装载点（bank）：图鉴第 3 页·大波比兄弟/风语大树 地图 |
| `0x18DC8` | `ending_03543e_load` | `loader.source_addr` | 2 | `rom_04c609` | `0x543E` → `rom_04c609.cpu_address=0x4609` | 图鉴页装载点（bank）：图鉴页·振翅蝙蝠等 + 城堡 图块集 |
| `0x18DCE` | `ending_03543e_load` | `loader.bank` | 1 | `rom_04c609` | `0x0D` → `rom_04c609.bank=0x13` | 图鉴页装载点（bank）：图鉴页·振翅蝙蝠等 + 城堡 图块集 |
| `0x18DD3` | `ending_035987_load` | `loader.source_addr` | 2 | `rom_04caf2` | `0x5987` → `rom_04caf2.cpu_address=0x4AF2` | 图鉴页装载点（bank）：图鉴页·振翅蝙蝠等 + 城堡 地图（蝙蝠页） |
| `0x18DD9` | `ending_035987_load` | `loader.bank` | 1 | `rom_04caf2` | `0x0D` → `rom_04caf2.bank=0x13` | 图鉴页装载点（bank）：图鉴页·振翅蝙蝠等 + 城堡 地图（蝙蝠页） |
| `0x18DF8` | `ending_035a89_load` | `loader.source_addr` | 2 | `rom_04954a` | `0x5A89` → `rom_04954a.cpu_address=0x554A` | 图鉴页装载点（bank）：图鉴页·箩箩箩/菈菈菈 + 城堡 图块集 |
| `0x18DFE` | `ending_035a89_load` | `loader.bank` | 1 | `rom_04954a` | `0x0D` → `rom_04954a.bank=0x12` | 图鉴页装载点（bank）：图鉴页·箩箩箩/菈菈菈 + 城堡 图块集 |
| `0x18E03` | `ending_035fd2_load` | `loader.source_addr` | 2 | `rom_0496d4` | `0x5FD2` → `rom_0496d4.cpu_address=0x56D4` | 图鉴页装载点（bank）：图鉴页·箩箩箩/菈菈菈 + 城堡 地图 |
| `0x18E09` | `ending_035fd2_load` | `loader.bank` | 1 | `rom_0496d4` | `0x0D` → `rom_0496d4.bank=0x12` | 图鉴页装载点（bank）：图鉴页·箩箩箩/菈菈菈 + 城堡 地图 |
| `0x18E30` | `ending_036063_load` | `loader.source_addr` | 2 | `rom_049769` | `0x6063` → `rom_049769.cpu_address=0x5769` | 图鉴页装载点（bank）：图鉴页·蛙镜鱼等 + 树林 图块集 |
| `0x18E36` | `ending_036063_load` | `loader.bank` | 1 | `rom_049769` | `0x0D` → `rom_049769.bank=0x12` | 图鉴页装载点（bank）：图鉴页·蛙镜鱼等 + 树林 图块集 |
| `0x18E3B` | `ending_036553_load` | `loader.source_addr` | 2 | `rom_049bf8` | `0x6553` → `rom_049bf8.cpu_address=0x5BF8` | 图鉴页装载点（bank）：图鉴页·蛙镜鱼等 + 树林 地图 |
| `0x18E41` | `ending_036553_load` | `loader.bank` | 1 | `rom_049bf8` | `0x0D` → `rom_049bf8.bank=0x12` | 图鉴页装载点（bank）：图鉴页·蛙镜鱼等 + 树林 地图 |
| `0x18E60` | `ending_036658_load` | `loader.source_addr` | 2 | `rom_04cc04` | `0x6658` → `rom_04cc04.cpu_address=0x4C04` | 图鉴页装载点（bank）：图鉴页·卡钸拉 + 云 图块集 |
| `0x18E66` | `ending_036658_load` | `loader.bank` | 1 | `rom_04cc04` | `0x0D` → `rom_04cc04.bank=0x13` | 图鉴页装载点（bank）：图鉴页·卡钸拉 + 云 图块集 |
| `0x18E6B` | `ending_036b80_load` | `loader.source_addr` | 2 | `rom_04cd98` | `0x6B80` → `rom_04cd98.cpu_address=0x4D98` | 图鉴页装载点（bank）：图鉴页·卡钸拉 + 云 地图 |
| `0x18E71` | `ending_036b80_load` | `loader.bank` | 1 | `rom_04cd98` | `0x0D` → `rom_04cd98.bank=0x13` | 图鉴页装载点（bank）：图鉴页·卡钸拉 + 云 地图 |
| `0x18E98` | `ending_036c7c_load` | `loader.source_addr` | 2 | `rom_049f9a` | `0x6C7C` → `rom_049f9a.cpu_address=0x5F9A` | 图鉴页装载点（bank）：图鉴页·疯狂鬼面等 + 城市 图块集 |
| `0x18E9E` | `ending_036c7c_load` | `loader.bank` | 1 | `rom_049f9a` | `0x0D` → `rom_049f9a.bank=0x12` | 图鉴页装载点（bank）：图鉴页·疯狂鬼面等 + 城市 图块集 |
| `0x18EA3` | `ending_03717d_load` | `loader.source_addr` | 2 | `rom_04a3a1` | `0x717D` → `rom_04a3a1.cpu_address=0x63A1` | 图鉴页装载点（bank）：图鉴页·疯狂鬼面等 + 城市 地图 |
| `0x18EA9` | `ending_03717d_load` | `loader.bank` | 1 | `rom_04a3a1` | `0x0D` → `rom_04a3a1.bank=0x12` | 图鉴页装载点（bank）：图鉴页·疯狂鬼面等 + 城市 地图 |
| `0x18EC8` | `ending_03729b_load` | `loader.source_addr` | 2 | `rom_04ce8c` | `0x729B` → `rom_04ce8c.cpu_address=0x4E8C` | 图鉴页装载点（bank）：图鉴页·独眼云 + 星空 图块集 |
| `0x18ECE` | `ending_03729b_load` | `loader.bank` | 1 | `rom_04ce8c` | `0x0D` → `rom_04ce8c.bank=0x13` | 图鉴页装载点（bank）：图鉴页·独眼云 + 星空 图块集 |
| `0x18ED3` | `ending_03779c_load` | `loader.source_addr` | 2 | `rom_04d0bb` | `0x779C` → `rom_04d0bb.cpu_address=0x50BB` | 图鉴页装载点（bank）：图鉴页·独眼云 + 星空 地图 |
| `0x18ED9` | `ending_03779c_load` | `loader.bank` | 1 | `rom_04d0bb` | `0x0D` → `rom_04d0bb.bank=0x13` | 图鉴页装载点（bank）：图鉴页·独眼云 + 星空 地图 |
| `0x18EFF` | `ending_038000_load` | `loader.source_addr` | 2 | `rom_04a7e9` | `0x4000` → `rom_04a7e9.cpu_address=0x67E9` | 图鉴页装载点（bank）：图鉴页·喔喔鸡等 + 树林 图块集 |
| `0x18F05` | `ending_038000_load` | `loader.bank` | 1 | `rom_04a7e9` | `0x0E` → `rom_04a7e9.bank=0x12` | 图鉴页装载点（bank）：图鉴页·喔喔鸡等 + 树林 图块集 |
| `0x18F0A` | `ending_0378cc_load` | `loader.source_addr` | 2 | `rom_04ab1b` | `0x78CC` → `rom_04ab1b.cpu_address=0x6B1B` | 图鉴页装载点（bank）：图鉴页·喔喔鸡等 + 树林 地图 |
| `0x18F10` | `ending_0378cc_load` | `loader.bank` | 1 | `rom_04ab1b` | `0x0D` → `rom_04ab1b.bank=0x12` | 图鉴页装载点（bank）：图鉴页·喔喔鸡等 + 树林 地图 |
| `0x18F37` | `ending_038582_load` | `loader.source_addr` | 2 | `rom_04d1b8` | `0x4582` → `rom_04d1b8.cpu_address=0x51B8` | 图鉴页装载点（bank）：图鉴页·睡帽幽灵等 + 砖墙 图块集 |
| `0x18F3D` | `ending_038582_load` | `loader.bank` | 1 | `rom_04d1b8` | `0x0E` → `rom_04d1b8.bank=0x13` | 图鉴页装载点（bank）：图鉴页·睡帽幽灵等 + 砖墙 图块集 |
| `0x18F42` | `ending_038ac6_load` | `loader.source_addr` | 2 | `rom_04d586` | `0x4AC6` → `rom_04d586.cpu_address=0x5586` | 图鉴页装载点（bank）：图鉴页·睡帽幽灵等 + 砖墙 地图 |
| `0x18F48` | `ending_038ac6_load` | `loader.bank` | 1 | `rom_04d586` | `0x0E` → `rom_04d586.bank=0x13` | 图鉴页装载点（bank）：图鉴页·睡帽幽灵等 + 砖墙 地图 |
| `0x18F6F` | `ending_038bf3_load` | `loader.source_addr` | 2 | `rom_04b11e` | `0x4BF3` → `rom_04b11e.cpu_address=0x711E` | 图鉴页装载点（bank）：图鉴页·章鱼怪等 + 海与船 图块集 |
| `0x18F75` | `ending_038bf3_load` | `loader.bank` | 1 | `rom_04b11e` | `0x0E` → `rom_04b11e.bank=0x12` | 图鉴页装载点（bank）：图鉴页·章鱼怪等 + 海与船 图块集 |
| `0x18F7A` | `ending_03911e_load` | `loader.source_addr` | 2 | `rom_04b4db` | `0x511E` → `rom_04b4db.cpu_address=0x74DB` | 图鉴页装载点（bank）：图鉴页·章鱼怪等 + 海与船 地图 |
| `0x18F80` | `ending_03911e_load` | `loader.bank` | 1 | `rom_04b4db` | `0x0E` → `rom_04b4db.bank=0x12` | 图鉴页装载点（bank）：图鉴页·章鱼怪等 + 海与船 地图 |
| `0x18FA7` | `ending_039206_load` | `loader.source_addr` | 2 | `rom_04b5dd` | `0x5206` → `rom_04b5dd.cpu_address=0x75DD` | 图鉴页装载点（bank）：图鉴页·子弹鹈鹕等 + 星空 图块集 |
| `0x18FAD` | `ending_039206_load` | `loader.bank` | 1 | `rom_04b5dd` | `0x0E` → `rom_04b5dd.bank=0x12` | 图鉴页装载点（bank）：图鉴页·子弹鹈鹕等 + 星空 图块集 |
| `0x18FB2` | `ending_039707_load` | `loader.source_addr` | 2 | `rom_04b943` | `0x5707` → `rom_04b943.cpu_address=0x7943` | 图鉴页装载点（bank）：图鉴页·子弹鹈鹕等 + 星空 地图 |
| `0x18FB8` | `ending_039707_load` | `loader.bank` | 1 | `rom_04b943` | `0x0E` → `rom_04b943.bank=0x12` | 图鉴页装载点（bank）：图鉴页·子弹鹈鹕等 + 星空 地图 |
| `0x18FE2` | `ending_039820_load` | `loader.source_addr` | 2 | `rom_04d6b7` | `0x5820` → `rom_04d6b7.cpu_address=0x56B7` | 图鉴页装载点（bank）：图鉴页·帝帝帝大王 + 王冠舞台 图块集 |
| `0x18FE8` | `ending_039820_load` | `loader.bank` | 1 | `rom_04d6b7` | `0x0E` → `rom_04d6b7.bank=0x13` | 图鉴页装载点（bank）：图鉴页·帝帝帝大王 + 王冠舞台 图块集 |
| `0x18FED` | `ending_039be1_load` | `loader.source_addr` | 2 | `rom_04d918` | `0x5BE1` → `rom_04d918.cpu_address=0x5918` | 图鉴页装载点（bank）：图鉴页·帝帝帝大王 + 王冠舞台 地图 |
| `0x18FF3` | `ending_039be1_load` | `loader.bank` | 1 | `rom_04d918` | `0x0E` → `rom_04d918.bank=0x13` | 图鉴页装载点（bank）：图鉴页·帝帝帝大王 + 王冠舞台 地图 |
| `0x19032` | `ending_039cbf_load_pointer` | `loader.source_addr` | 2 | `rom_055130` | `0x5CBF` → `rom_055130.cpu_address=0x5130` | 图鉴/提示页装载指针（地址+bank）：额外模式通关提示 图块集（整屏 384 图块） |
| `0x19038` | `ending_039cbf_load_pointer` | `loader.bank` | 1 | `rom_055130` | `0x0E` → `rom_055130.bank=0x15` | 图鉴/提示页装载指针（地址+bank）：额外模式通关提示 图块集（整屏 384 图块） |
| `0x1903D` | `ending_03acec_load_pointer` | `loader.source_addr` | 2 | `rom_056110` | `0x6CEC` → `rom_056110.cpu_address=0x6110` | 图鉴/提示页装载指针（地址+bank）：额外模式通关提示 地图 |
| `0x19043` | `ending_03acec_load_pointer` | `loader.bank` | 1 | `rom_056110` | `0x0E` → `rom_056110.bank=0x15` | 图鉴/提示页装载指针（地址+bank）：额外模式通关提示 地图 |
| `0x19063` | `ending_03adda_load_pointer` | `loader.source_addr` | 2 | `rom_054000` | `0x6DDA` → `rom_054000.cpu_address=0x4000` | 图鉴/提示页装载指针（地址+bank）：普通模式通关提示 图块集（整屏 384 图块） |
| `0x19069` | `ending_03adda_load_pointer` | `loader.bank` | 1 | `rom_054000` | `0x0E` → `rom_054000.bank=0x15` | 图鉴/提示页装载指针（地址+bank）：普通模式通关提示 图块集（整屏 384 图块） |
| `0x1906E` | `ending_03be31_load_pointer` | `loader.source_addr` | 2 | `rom_055050` | `0x7E31` → `rom_055050.cpu_address=0x5050` | 图鉴/提示页装载指针（地址+bank）：普通模式通关提示 地图 |
| `0x19074` | `ending_03be31_load_pointer` | `loader.bank` | 1 | `rom_055050` | `0x0E` → `rom_055050.bank=0x15` | 图鉴/提示页装载指针（地址+bank）：普通模式通关提示 地图 |
| `0x1A3A2` | `normal_hud_load` | `loader.source_addr` | 2 | `rom_041000` | `0x4855` → `rom_041000.cpu_address=0x5000` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x1A3A8` | `normal_hud_load` | `loader.bank` | 1 | `rom_041000` | `0x02` → `rom_041000.bank=0x10` | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `0x1A3C3` | `configuration_map_full_bundle_load` | `loader.source_addr` | 2 | `rom_05c000` | `0x453A` → `rom_05c000.cpu_address=0x4000` | 配置整包装载：源 bank 3→23，VRAM 目的 0x9800→0x8800 |
| `0x1A3C7` | `configuration_map_full_bundle_load` | `loader.vram_base` | 1 | `rom_05c000` | `0x98` → `0x88` | 配置整包装载：源 bank 3→23，VRAM 目的 0x9800→0x8800 |
| `0x1A3C9` | `configuration_map_full_bundle_load` | `loader.bank` | 1 | `rom_05c000` | `0x03` → `rom_05c000.bank=0x17` | 配置整包装载：源 bank 3→23，VRAM 目的 0x9800→0x8800 |
| `0x1A56E` | `sound_test_map_load` | `loader.source_addr` | 2 | `rom_0438f6` | `0x44C2` → `rom_0438f6.cpu_address=0x78F6` | 声音测试整包装载（VRAM 目的 0x9800→0x9000） |
| `0x1A572` | `sound_test_map_load` | `loader.vram_base` | 1 | `rom_0438f6` | `0x98` → `0x90` | 声音测试整包装载（VRAM 目的 0x9800→0x9000） |
| `0x1A574` | `sound_test_map_load` | `loader.bank` | 1 | `rom_0438f6` | `0x03` → `rom_0438f6.bank=0x10` | 声音测试整包装载（VRAM 目的 0x9800→0x9000） |

## 04 装载目的地址

改装载到 VRAM 的高字节，让新图块集/地图落在正确的 0x8000/0x8800/0x9000。

| 偏移 | site | kind | 字节 | 资源 | 旧 → 新 | 说明 |
| --- | --- | --- | ---: | --- | --- | --- |
| `0x1804E` | `title_bundle_load` | `loader.vram_base` | 1 | `rom_070000` | `0x98` → `0x88` | 标题整包装载：源 bank 3→28，VRAM 目的 0x9800→0x8800 |
| `0x18372` | `stage_bundle_destination` | `loader.vram_base` | 1 | `-` | `0x98` → `0x90` | 关卡整包装载目的 0x9800→0x9000（图块 0x9000–0x97FF，地图接 0x9800） |
| `0x1876A` | `gameover_map_load` | `loader.vram_base` | 1 | `rom_04454c` | `0x98` → `0x90` | GAME OVER 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x187F0` | `continue_map_load` | `loader.vram_base` | 1 | `rom_044734` | `0x98` → `0x90` | CONTINUE 整包装载（VRAM 目的 0x9800→0x9000） |
| `0x1A3C7` | `configuration_map_full_bundle_load` | `loader.vram_base` | 1 | `rom_05c000` | `0x98` → `0x88` | 配置整包装载：源 bank 3→23，VRAM 目的 0x9800→0x8800 |
| `0x1A572` | `sound_test_map_load` | `loader.vram_base` | 1 | `rom_0438f6` | `0x98` → `0x90` | 声音测试整包装载（VRAM 目的 0x9800→0x9000） |

## 05 指针表与目的基址

五关介绍整包的三字节指针表，以及关卡整包的 VRAM 基址。

| 偏移 | site | kind | 字节 | 资源 | 旧 → 新 | 说明 |
| --- | --- | --- | ---: | --- | --- | --- |
| `0x190BB` | `stage_1_bundle_pointer` | `stage.pointer_table` | 15 | `-` | `stage_1 6:0x7835, stage_2 6:0x78DD, stage_3 6:0x7958, stage_4 6:0x79EF, stage_5 6:0x7AA6` → `stage_1 27:0x4000, stage_2 27:0x470B, stage_3 27:0x4DA8, stage_4 27:0x5490, stage_5 27:0x5B85` | 五个关卡介绍整包的三字节指针表（[bank][addr_hi][addr_lo] ×5） |

## 06 UI/精灵微调

HUD 标签图块号重排、图鉴蝙蝠精灵 X 坐标 -9px。

| 偏移 | site | kind | 字节 | 资源 | 旧 → 新 | 说明 |
| --- | --- | --- | ---: | --- | --- | --- |
| `0x02011` | `HUD_score_label_x16` | `hud.label_tile` | 1 | `-` | `0x02` → `0x04` | HUD 标签图块号重排，使“得分”左对齐 |
| `0x02016` | `HUD_score_label_x16` | `hud.label_tile` | 1 | `-` | `0x03` → `0x02` | HUD 标签图块号重排，使“得分”左对齐 |
| `0x0201A` | `HUD_score_label_x16` | `hud.label_tile` | 1 | `-` | `0x04` → `0x03` | HUD 标签图块号重排，使“得分”左对齐 |
| `0x3DA1F` | `gallery_page4_bat_x_only` | `sprite.x` | 1 | `-` | `0xF8` → `0xEF` | 只改这一专用横坐标，文字不动 |

## 07 资源内容

新增/替换的压缩图块集、地图、整包页（构建输入是 PNG，不是 hex）。

| id | label | format | role | bank | offset | capacity | packed | 页面 | 用途 |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |
| `rom_041000` | `normal_hud` | sheet | active | 16 | `0x41000` | 259 | 259 | `03_Image/edits/rom_041000.json` | 普通模式 HUD 字形条 |
| `rom_041103` | `extra_hud` | sheet | active | 16 | `0x41103` | 259 | 259 | `03_Image/edits/rom_041103.json` | 额外模式 HUD 字形条 |
| `rom_0438f6` | `sound_test_map` | bundle | active | 16 | `0x438F6` | 1802 | 713 | `03_Image/pages/rom_0438f6.png` | 声音测试页 |
| `rom_04454c` | `gameover_map` | bundle | active | 17 | `0x4454C` | 488 | 488 | `03_Image/pages/rom_04454c.png` | GAME OVER 画面 |
| `rom_044734` | `continue_map` | bundle | active | 17 | `0x44734` | 14540 | 478 | `03_Image/pages/rom_044734.png` | CONTINUE 画面 |
| `rom_048000` | `ending_034000` | tileset | active | 18 | `0x48000` | 1122 | 1122 | `-` | 图鉴页·黑刺球等 + 蘑菇林 图块集 |
| `rom_048462` | `ending_0345c0` | tilemap | active | 18 | `0x48462` | 335 | 335 | `03_Image/edits/rom_048462.json` | 图鉴页·黑刺球等 + 蘑菇林 地图 |
| `rom_04954a` | `ending_035a89` | tileset | active | 18 | `0x4954A` | 394 | 394 | `-` | 图鉴页·箩箩箩/菈菈菈 + 城堡 图块集 |
| `rom_0496d4` | `ending_035fd2` | tilemap | active | 18 | `0x496D4` | 149 | 149 | `03_Image/edits/rom_0496d4.json` | 图鉴页·箩箩箩/菈菈菈 + 城堡 地图 |
| `rom_049769` | `ending_036063` | tileset | active | 18 | `0x49769` | 1167 | 1167 | `-` | 图鉴页·蛙镜鱼等 + 树林 图块集 |
| `rom_049bf8` | `ending_036553` | tilemap | active | 18 | `0x49BF8` | 285 | 285 | `03_Image/edits/rom_049bf8.json` | 图鉴页·蛙镜鱼等 + 树林 地图 |
| `rom_049f9a` | `ending_036c7c` | tileset | active | 18 | `0x49F9A` | 1031 | 1031 | `-` | 图鉴页·疯狂鬼面等 + 城市 图块集 |
| `rom_04a3a1` | `ending_03717d` | tilemap | active | 18 | `0x4A3A1` | 293 | 293 | `03_Image/edits/rom_04a3a1.json` | 图鉴页·疯狂鬼面等 + 城市 地图 |
| `rom_04a7e9` | `ending_038000` | tileset | active | 18 | `0x4A7E9` | 818 | 818 | `-` | 图鉴页·喔喔鸡等 + 树林 图块集 |
| `rom_04ab1b` | `ending_0378cc` | tilemap | active | 18 | `0x4AB1B` | 264 | 264 | `03_Image/edits/rom_04ab1b.json` | 图鉴页·喔喔鸡等 + 树林 地图 |
| `rom_04b11e` | `ending_038bf3` | tileset | active | 18 | `0x4B11E` | 957 | 957 | `-` | 图鉴页·章鱼怪等 + 海与船 图块集 |
| `rom_04b4db` | `ending_03911e` | tilemap | active | 18 | `0x4B4DB` | 258 | 258 | `03_Image/edits/rom_04b4db.json` | 图鉴页·章鱼怪等 + 海与船 地图 |
| `rom_04b5dd` | `ending_039206` | tileset | active | 18 | `0x4B5DD` | 870 | 870 | `-` | 图鉴页·子弹鹈鹕等 + 星空 图块集 |
| `rom_04b943` | `ending_039707` | tilemap | active | 18 | `0x4B943` | 306 | 306 | `03_Image/edits/rom_04b943.json` | 图鉴页·子弹鹈鹕等 + 星空 地图 |
| `rom_04c000` | `ending_0346fb` | tileset | active | 19 | `0x4C000` | 1268 | 1268 | `-` | 图鉴页·喳喳鸟等 + 山丘 图块集 |
| `rom_04c4f4` | `ending_034cb4` | tilemap | active | 19 | `0x4C4F4` | 277 | 277 | `03_Image/edits/rom_04c4f4.json` | 图鉴页·喳喳鸟等 + 山丘 地图 |
| `rom_04c609` | `ending_03543e` | tileset | active | 19 | `0x4C609` | 1257 | 1257 | `-` | 图鉴页·振翅蝙蝠等 + 城堡 图块集 |
| `rom_04caf2` | `ending_035987` | tilemap | active | 19 | `0x4CAF2` | 274 | 274 | `03_Image/edits/rom_04caf2.json` | 图鉴页·振翅蝙蝠等 + 城堡 地图（蝙蝠页） |
| `rom_04cc04` | `ending_036658` | tileset | active | 19 | `0x4CC04` | 404 | 404 | `-` | 图鉴页·卡钸拉 + 云 图块集 |
| `rom_04cd98` | `ending_036b80` | tilemap | active | 19 | `0x4CD98` | 244 | 244 | `03_Image/edits/rom_04cd98.json` | 图鉴页·卡钸拉 + 云 地图 |
| `rom_04ce8c` | `ending_03729b` | tileset | active | 19 | `0x4CE8C` | 559 | 559 | `-` | 图鉴页·独眼云 + 星空 图块集 |
| `rom_04d0bb` | `ending_03779c` | tilemap | active | 19 | `0x4D0BB` | 253 | 253 | `03_Image/edits/rom_04d0bb.json` | 图鉴页·独眼云 + 星空 地图 |
| `rom_04d1b8` | `ending_038582` | tileset | active | 19 | `0x4D1B8` | 974 | 974 | `-` | 图鉴页·睡帽幽灵等 + 砖墙 图块集 |
| `rom_04d586` | `ending_038ac6` | tilemap | active | 19 | `0x4D586` | 305 | 305 | `03_Image/edits/rom_04d586.json` | 图鉴页·睡帽幽灵等 + 砖墙 地图 |
| `rom_04d6b7` | `ending_039820` | tileset | active | 19 | `0x4D6B7` | 609 | 609 | `-` | 图鉴页·帝帝帝大王 + 王冠舞台 图块集 |
| `rom_04d918` | `ending_039be1` | tilemap | active | 19 | `0x4D918` | 9960 | 164 | `03_Image/edits/rom_04d918.json` | 图鉴页·帝帝帝大王 + 王冠舞台 地图 |
| `rom_050000` | `ending_sprites` | sheet | active | 20 | `0x50000` | 16384 | 2418 | `03_Image/edits/rom_050000.json` | 结局/通关提示精灵表（剧终牌等） |
| `rom_054000` | `ending_03adda` | tileset | active | 21 | `0x54000` | 4176 | 4165 | `-` | 普通模式通关提示 图块集（整屏 384 图块） |
| `rom_055050` | `ending_03be31` | tilemap | active | 21 | `0x55050` | 224 | 223 | `03_Image/edits/rom_055050.json` | 普通模式通关提示（提示如何进入额外模式） 地图 |
| `rom_055130` | `ending_039cbf` | tileset | active | 21 | `0x55130` | 4064 | 4057 | `-` | 额外模式通关提示 图块集（整屏 384 图块） |
| `rom_056110` | `ending_03acec` | tilemap | active | 21 | `0x56110` | 7920 | 215 | `03_Image/edits/rom_056110.json` | 额外模式通关提示（提示如何进入配置模式） 地图 |
| `rom_058000` | `intro_decoration` | sheet | active | 22 | `0x58000` | 16384 | 1268 | `03_Image/edits/rom_058000.json` | 关卡介绍右下角 32×16 中文角标（开场装饰） |
| `rom_05c000` | `configuration_bundle` | bundle | active | 23 | `0x5C000` | 16384 | 2559 | `03_Image/pages/rom_05c000.png` | 配置页整包（256 图块 + 地图） |
| `rom_06c000` | `stage_1` | bundle | active | 27 | `0x6C000` | 1803 | 1803 | `03_Image/pages/rom_06c000.png` | 场景 1 介绍整包（128 图块 + 地图） |
| `rom_06c70b` | `stage_2` | bundle | active | 27 | `0x6C70B` | 1693 | 1693 | `03_Image/pages/rom_06c70b.png` | 场景 2 介绍整包 |
| `rom_06cda8` | `stage_3` | bundle | active | 27 | `0x6CDA8` | 1768 | 1768 | `03_Image/pages/rom_06cda8.png` | 场景 3 介绍整包 |
| `rom_06d490` | `stage_4` | bundle | active | 27 | `0x6D490` | 1781 | 1781 | `03_Image/pages/rom_06d490.png` | 场景 4 介绍整包 |
| `rom_06db85` | `stage_5` | bundle | active | 27 | `0x6DB85` | 9339 | 1668 | `03_Image/pages/rom_06db85.png` | 场景 5 介绍整包（240 px 高） |
| `rom_070000` | `title_bundle` | bundle | active | 28 | `0x70000` | 16384 | 3186 | `03_Image/pages/rom_070000.png` | 标题画面整包（中文 Logo + 额外游戏 + 菜单） |
| `rom_074000` | `ending_034dc0` | tileset | active | 29 | `0x74000` | 691 | 691 | `-` | 图鉴第 3 页·大波比兄弟/风语大树 图块集 |
| `rom_0742b3` | `ending_03535c` | tilemap | active | 29 | `0x742B3` | 15693 | 231 | `03_Image/edits/rom_0742b3.json` | 图鉴第 3 页·大波比兄弟/风语大树 地图 |

## 08 文本层

可由“字体 + 译文 + 布局”重排的文本（76 条 / 26 页，其中 8 页提交去字底图）。

| 页面 | 文本 id | 译文 | 字体 | 存储 | 锚点 |
| --- | --- | --- | --- | --- | --- |
| `rom_041000` | `hud_kirby` | 卡比 | 8px | edit | (64, 0) |
| `rom_041000` | `hud_score` | 积分 | 8px | edit | (40, 0) |
| `rom_041103` | `hud_kirby` | 卡比 | 8px | edit | (64, 0) |
| `rom_041103` | `hud_score` | 积分 | 8px | edit | (40, 0) |
| `rom_0438f6` | `music` | 音乐 | 12px | page | (56, 54) |
| `rom_0438f6` | `sound` | 音效 | 12px | page | (56, 70) |
| `rom_0438f6` | `sound_test` | 声音测试 | 12px | page | (56, 30) |
| `rom_04454c` | `game_over` | 游戏结束 | 12px | page | (56, 46) |
| `rom_044734` | `continue` | 继续 | 12px | page | (56, 30) |
| `rom_044734` | `end` | 结束 | 12px | page | (56, 46) |
| `rom_048462` | `graphic_ending_01_01` | 黑刺球 | 12px | edit | (14, 42) |
| `rom_048462` | `graphic_ending_01_02` | 瓦豆鲁迪 | 12px | edit | (104, 50) |
| `rom_048462` | `graphic_ending_01_03` | 飞翅球球 | 12px | edit | (52, 58) |
| `rom_048462` | `graphic_ending_01_04` | 瓦豆鲁笃 | 12px | edit | (24, 82) |
| `rom_048462` | `graphic_ending_01_05` | 黑大炮 | 12px | edit | (78, 98) |
| `rom_0496d4` | `graphic_ending_05_01` | 箩箩箩 | 12px | edit | (38, 50) |
| `rom_0496d4` | `graphic_ending_05_02` | 菈菈菈 | 12px | edit | (102, 82) |
| `rom_049bf8` | `graphic_ending_06_01` | 蛙镜鱼 | 12px | edit | (70, 42) |
| `rom_049bf8` | `graphic_ending_06_02` | 石像怪 | 12px | edit | (22, 58) |
| `rom_049bf8` | `graphic_ending_06_03` | 乌贼怪 | 12px | edit | (110, 66) |
| `rom_049bf8` | `graphic_ending_06_04` | 圆锥寄居蟹 | 12px | edit | (10, 98) |
| `rom_049bf8` | `graphic_ending_06_05` | 光束贝 | 12px | edit | (86, 98) |
| `rom_04a3a1` | `graphic_ending_08_01` | 膨胀云 | 12px | edit | (94, 50) |
| `rom_04a3a1` | `graphic_ending_08_02` | 疯狂鬼面 | 12px | edit | (40, 58) |
| `rom_04a3a1` | `graphic_ending_08_03` | 尖耳怪 | 12px | edit | (102, 82) |
| `rom_04a3a1` | `graphic_ending_08_04` | 晕晕怪 | 12px | edit | (30, 90) |
| `rom_04a3a1` | `graphic_ending_08_05` | 弯刀骑士 | 12px | edit | (64, 106) |
| `rom_04ab1b` | `graphic_ending_10_01` | 喔喔鸡 | 12px | edit | (62, 42) |
| `rom_04ab1b` | `graphic_ending_10_02` | 振翅球球 | 12px | edit | (32, 82) |
| `rom_04ab1b` | `graphic_ending_10_03` | 蛋糕怪 | 12px | edit | (100, 106) |
| `rom_04b4db` | `graphic_ending_12_01` | 章鱼怪 | 12px | edit | (22, 42) |
| `rom_04b4db` | `graphic_ending_12_02` | 暴躁石像 | 12px | edit | (88, 50) |
| `rom_04b4db` | `graphic_ending_12_03` | 独眼蟹 | 12px | edit | (38, 74) |
| `rom_04b4db` | `graphic_ending_12_04` | 连射炮 | 12px | edit | (94, 90) |
| `rom_04b943` | `graphic_ending_13_01` | 子弹鹈鹕 | 12px | edit | (80, 42) |
| `rom_04b943` | `graphic_ending_13_02` | 胡须猫 | 12px | edit | (30, 66) |
| `rom_04b943` | `graphic_ending_13_03` | 本尼 | 12px | edit | (116, 90) |
| `rom_04b943` | `graphic_ending_13_04` | 武魔 | 12px | edit | (68, 98) |
| `rom_04c4f4` | `graphic_ending_02_01` | 喳喳鸟 | 12px | edit | (30, 50) |
| `rom_04c4f4` | `graphic_ending_02_02` | 头带熊 | 12px | edit | (94, 76) |
| `rom_04c4f4` | `graphic_ending_02_03` | 蘑菇怪 | 12px | edit | (52, 90) |
| `rom_04c4f4` | `graphic_ending_02_04` | 小波比兄弟 | 12px | edit | (4, 106) |
| `rom_04caf2` | `graphic_ending_04_01` | 振翅蝙蝠 | 12px | edit | (16, 42) |
| `rom_04caf2` | `graphic_ending_04_02` | 绿海葵 | 12px | edit | (110, 50) |
| `rom_04caf2` | `graphic_ending_04_03` | 芒比尸 | 12px | edit | (54, 66) |
| `rom_04caf2` | `graphic_ending_04_04` | 魔扫把 | 12px | edit | (14, 82) |
| `rom_04caf2` | `graphic_ending_04_05` | 两面派 | 12px | edit | (110, 82) |
| `rom_04caf2` | `graphic_ending_04_06` | 吐舌箱 | 12px | edit | (62, 98) |
| `rom_04caf2` | `graphic_ending_04_07` | 惊吓幽灵 | 12px | edit | (96, 114) |
| `rom_04cd98` | `graphic_ending_07_01` | 卡钸拉 | 12px | edit | (74, 78) |
| `rom_04d0bb` | `graphic_ending_09_01` | 独眼云 | 12px | edit | (44, 74) |
| `rom_04d586` | `graphic_ending_11_01` | P瓜先生 | 12px | edit | (99, 58) |
| `rom_04d586` | `graphic_ending_11_02` | 睡帽幽灵 | 12px | edit | (8, 66) |
| `rom_04d586` | `graphic_ending_11_03` | 冒出箱 | 12px | edit | (30, 98) |
| `rom_04d586` | `graphic_ending_11_04` | 骷髅头 | 12px | edit | (94, 90) |
| `rom_04d918` | `graphic_ending_14_01` | 帝帝帝大王 | 12px | edit | (50, 112) |
| `rom_055050` | `graphic_ending_16_01` | 额外⏎游戏 | 8px | edit | (24, 8) |
| `rom_055050` | `graphic_ending_16_02` | 恭喜⏎通关！ | 8px | edit | (96, 8) |
| `rom_055050` | `graphic_ending_16_03` | 在标题界面⏎输入左侧指令， | 8px | edit | (88, 32) |
| `rom_055050` | `graphic_ending_16_04` | 踏上⏎新的⏎冒险吧！ | 8px | edit | (88, 56) |
| `rom_056110` | `graphic_ending_15_01` | 配置⏎模式 | 8px | edit | (24, 8) |
| `rom_056110` | `graphic_ending_15_02` | 水平⏎真不错呢， | 8px | edit | (88, 8) |
| `rom_056110` | `graphic_ending_15_03` | 送你一份⏎特别的礼物♪ | 8px | edit | (88, 32) |
| `rom_056110` | `graphic_ending_15_04` | 感谢⏎您的游玩！ | 8px | edit | (88, 56) |
| `rom_06c000` | `stage_1_name` | 葛绿谷绿 | 12px | page | (56, 38) |
| `rom_06c000` | `stage_1_number` | 场景1 | 12px | page | (62, 12) |
| `rom_06c70b` | `stage_2_name` | 箩箩箩的城堡 | 12px | page | (44, 38) |
| `rom_06c70b` | `stage_2_number` | 场景2 | 12px | page | (62, 12) |
| `rom_06cda8` | `stage_3_name` | 漂浮岛屿 | 12px | page | (56, 38) |
| `rom_06cda8` | `stage_3_number` | 场景3 | 12px | page | (62, 12) |
| `rom_06d490` | `stage_4_name` | 泡泡云层 | 12px | page | (56, 38) |
| `rom_06d490` | `stage_4_number` | 场景4 | 12px | page | (62, 12) |
| `rom_06db85` | `stage_5_name` | 帝帝帝山 | 12px | page | (56, 36) |
| `rom_06db85` | `stage_5_number` | 场景5 | 12px | page | (62, 18) |
| `rom_0742b3` | `graphic_ending_03_01` | 大波比兄弟 | 12px | edit | (12, 92) |
| `rom_0742b3` | `graphic_ending_03_02` | 风语大树 | 12px | edit | (80, 114) |

## 09 构建与发布

构建→校验→xdelta3 增量→发布校验和。

- `python 00_Tools/build.py`：按清单装载 71 个资源、写入 116 处补丁、重算校验和；
- `python 00_Tools/verify.py`：核对 524288 字节与目标 SHA-256；
- `python 00_Tools/release.py`：生成相对 `baserom.gb` 的 xdelta3；
- `SHA256SUMS.txt`：固定 ROM / 补丁 / baserom 三个哈希。

## 附录 A：全部 116 处补丁

| # | 偏移 | kind | 字节 | 旧字节 → 新字节 |
| ---: | --- | --- | ---: | --- |
| 1 | `0x00148` | `rom.size` | 1 | `0x03` → `0x04` |
| 2 | `0x01B44` | `loader.source_addr` | 2 | `0x5548` → `0x0050` |
| 3 | `0x01B4A` | `loader.bank` | 1 | `0x02` → `0x10` |
| 4 | `0x01B5C` | `loader.source_addr` | 2 | `0x6648` → `0x0351` |
| 5 | `0x01B62` | `loader.bank` | 1 | `0x0a` → `0x10` |
| 6 | `0x02011` | `hud.label_tile` | 1 | `0x02` → `0x04` |
| 7 | `0x02016` | `hud.label_tile` | 1 | `0x03` → `0x02` |
| 8 | `0x0201A` | `hud.label_tile` | 1 | `0x04` → `0x03` |
| 9 | `0x18030` | `code.nop` | 3 | `0xcdc120` → `0x000000` |
| 10 | `0x1803B` | `code.nop` | 3 | `0xcdc120` → `0x000000` |
| 11 | `0x18046` | `code.nop` | 3 | `0xcdc120` → `0x000000` |
| 12 | `0x1804E` | `loader.vram_base` | 1 | `0x98` → `0x88` |
| 13 | `0x18050` | `loader.bank` | 1 | `0x03` → `0x1c` |
| 14 | `0x180A6` | `code.region` | 1 | `0x45` → `0x47` |
| 15 | `0x180A8` | `code.region` | 10 | `0x11ca402100cb3e0af578` → `0x2100cb16d41e0c782279` |
| 16 | `0x180B3` | `code.region` | 1 | `0x79` → `0x7a` |
| 17 | `0x180B5` | `code.region` | 20 | `0x1a221303f13d20f3afea1ecbfa91ffcbd7ea91ff` → `0x140c7bfe0720020e671d20eeaf77f091cbd7e091` |
| 18 | `0x18297` | `loader.source_addr` | 2 | `0x5548` → `0x0050` |
| 19 | `0x1829D` | `loader.bank` | 1 | `0x02` → `0x10` |
| 20 | `0x182AF` | `loader.source_addr` | 2 | `0x6648` → `0x0351` |
| 21 | `0x182B5` | `loader.bank` | 1 | `0x0a` → `0x10` |
| 22 | `0x18311` | `loader.source_addr` | 2 | `0x5548` → `0x0050` |
| 23 | `0x18317` | `loader.bank` | 1 | `0x02` → `0x10` |
| 24 | `0x18351` | `loader.source_addr` | 2 | `0xad5c` → `0x0040` |
| 25 | `0x18357` | `loader.bank` | 1 | `0x03` → `0x16` |
| 26 | `0x18372` | `loader.vram_base` | 1 | `0x98` → `0x90` |
| 27 | `0x18766` | `loader.source_addr` | 2 | `0x1646` → `0x4c45` |
| 28 | `0x1876A` | `loader.vram_base` | 1 | `0x98` → `0x90` |
| 29 | `0x1876C` | `loader.bank` | 1 | `0x03` → `0x11` |
| 30 | `0x187E1` | `loader.source_addr` | 2 | `0xad5c` → `0x0040` |
| 31 | `0x187E7` | `loader.bank` | 1 | `0x03` → `0x16` |
| 32 | `0x187EC` | `loader.source_addr` | 2 | `0x6646` → `0x3447` |
| 33 | `0x187F0` | `loader.vram_base` | 1 | `0x98` → `0x90` |
| 34 | `0x187F2` | `loader.bank` | 1 | `0x03` → `0x11` |
| 35 | `0x188B2` | `loader.source_addr` | 2 | `0x804f` → `0x0040` |
| 36 | `0x188B8` | `loader.bank` | 1 | `0x03` → `0x14` |
| 37 | `0x1890A` | `loader.source_addr` | 2 | `0x5548` → `0x0050` |
| 38 | `0x18910` | `loader.bank` | 1 | `0x02` → `0x10` |
| 39 | `0x18989` | `loader.source_addr` | 2 | `0x804f` → `0x0040` |
| 40 | `0x1898F` | `loader.bank` | 1 | `0x03` → `0x14` |
| 41 | `0x18D36` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 42 | `0x18D3B` | `loader.source_addr` | 2 | `0xc045` → `0x6244` |
| 43 | `0x18D41` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 44 | `0x18D60` | `loader.source_addr` | 2 | `0xfb46` → `0x0040` |
| 45 | `0x18D66` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 46 | `0x18D6B` | `loader.source_addr` | 2 | `0xb44c` → `0xf444` |
| 47 | `0x18D71` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 48 | `0x18D90` | `loader.source_addr` | 2 | `0xc04d` → `0x0040` |
| 49 | `0x18D96` | `loader.bank` | 1 | `0x0d` → `0x1d` |
| 50 | `0x18D9B` | `loader.source_addr` | 2 | `0x5c53` → `0xb342` |
| 51 | `0x18DA1` | `loader.bank` | 1 | `0x0d` → `0x1d` |
| 52 | `0x18DC8` | `loader.source_addr` | 2 | `0x3e54` → `0x0946` |
| 53 | `0x18DCE` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 54 | `0x18DD3` | `loader.source_addr` | 2 | `0x8759` → `0xf24a` |
| 55 | `0x18DD9` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 56 | `0x18DF8` | `loader.source_addr` | 2 | `0x895a` → `0x4a55` |
| 57 | `0x18DFE` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 58 | `0x18E03` | `loader.source_addr` | 2 | `0xd25f` → `0xd456` |
| 59 | `0x18E09` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 60 | `0x18E30` | `loader.source_addr` | 2 | `0x6360` → `0x6957` |
| 61 | `0x18E36` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 62 | `0x18E3B` | `loader.source_addr` | 2 | `0x5365` → `0xf85b` |
| 63 | `0x18E41` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 64 | `0x18E60` | `loader.source_addr` | 2 | `0x5866` → `0x044c` |
| 65 | `0x18E66` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 66 | `0x18E6B` | `loader.source_addr` | 2 | `0x806b` → `0x984d` |
| 67 | `0x18E71` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 68 | `0x18E98` | `loader.source_addr` | 2 | `0x7c6c` → `0x9a5f` |
| 69 | `0x18E9E` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 70 | `0x18EA3` | `loader.source_addr` | 2 | `0x7d71` → `0xa163` |
| 71 | `0x18EA9` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 72 | `0x18EC8` | `loader.source_addr` | 2 | `0x9b72` → `0x8c4e` |
| 73 | `0x18ECE` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 74 | `0x18ED3` | `loader.source_addr` | 2 | `0x9c77` → `0xbb50` |
| 75 | `0x18ED9` | `loader.bank` | 1 | `0x0d` → `0x13` |
| 76 | `0x18EFF` | `loader.source_addr` | 2 | `0x0040` → `0xe967` |
| 77 | `0x18F05` | `loader.bank` | 1 | `0x0e` → `0x12` |
| 78 | `0x18F0A` | `loader.source_addr` | 2 | `0xcc78` → `0x1b6b` |
| 79 | `0x18F10` | `loader.bank` | 1 | `0x0d` → `0x12` |
| 80 | `0x18F37` | `loader.source_addr` | 2 | `0x8245` → `0xb851` |
| 81 | `0x18F3D` | `loader.bank` | 1 | `0x0e` → `0x13` |
| 82 | `0x18F42` | `loader.source_addr` | 2 | `0xc64a` → `0x8655` |
| 83 | `0x18F48` | `loader.bank` | 1 | `0x0e` → `0x13` |
| 84 | `0x18F6F` | `loader.source_addr` | 2 | `0xf34b` → `0x1e71` |
| 85 | `0x18F75` | `loader.bank` | 1 | `0x0e` → `0x12` |
| 86 | `0x18F7A` | `loader.source_addr` | 2 | `0x1e51` → `0xdb74` |
| 87 | `0x18F80` | `loader.bank` | 1 | `0x0e` → `0x12` |
| 88 | `0x18FA7` | `loader.source_addr` | 2 | `0x0652` → `0xdd75` |
| 89 | `0x18FAD` | `loader.bank` | 1 | `0x0e` → `0x12` |
| 90 | `0x18FB2` | `loader.source_addr` | 2 | `0x0757` → `0x4379` |
| 91 | `0x18FB8` | `loader.bank` | 1 | `0x0e` → `0x12` |
| 92 | `0x18FE2` | `loader.source_addr` | 2 | `0x2058` → `0xb756` |
| 93 | `0x18FE8` | `loader.bank` | 1 | `0x0e` → `0x13` |
| 94 | `0x18FED` | `loader.source_addr` | 2 | `0xe15b` → `0x1859` |
| 95 | `0x18FF3` | `loader.bank` | 1 | `0x0e` → `0x13` |
| 96 | `0x19032` | `loader.source_addr` | 2 | `0xbf5c` → `0x3051` |
| 97 | `0x19038` | `loader.bank` | 1 | `0x0e` → `0x15` |
| 98 | `0x1903D` | `loader.source_addr` | 2 | `0xec6c` → `0x1061` |
| 99 | `0x19043` | `loader.bank` | 1 | `0x0e` → `0x15` |
| 100 | `0x19063` | `loader.source_addr` | 2 | `0xda6d` → `0x0040` |
| 101 | `0x19069` | `loader.bank` | 1 | `0x0e` → `0x15` |
| 102 | `0x1906E` | `loader.source_addr` | 2 | `0x317e` → `0x5050` |
| 103 | `0x19074` | `loader.bank` | 1 | `0x0e` → `0x15` |
| 104 | `0x190BB` | `stage.pointer_table` | 15 | `0x0678350678dd0679580679ef067aa6` → `0x1b40001b470b1b4da81b54901b5b85` |
| 105 | `0x1A3A2` | `loader.source_addr` | 2 | `0x5548` → `0x0050` |
| 106 | `0x1A3A8` | `loader.bank` | 1 | `0x02` → `0x10` |
| 107 | `0x1A3A9` | `code.nop` | 3 | `0xcdc120` → `0x000000` |
| 108 | `0x1A3B4` | `code.nop` | 3 | `0xcdc120` → `0x000000` |
| 109 | `0x1A3BF` | `code.nop` | 3 | `0xcdc120` → `0x000000` |
| 110 | `0x1A3C3` | `loader.source_addr` | 2 | `0x3a45` → `0x0040` |
| 111 | `0x1A3C7` | `loader.vram_base` | 1 | `0x98` → `0x88` |
| 112 | `0x1A3C9` | `loader.bank` | 1 | `0x03` → `0x17` |
| 113 | `0x1A56E` | `loader.source_addr` | 2 | `0xc244` → `0xf678` |
| 114 | `0x1A572` | `loader.vram_base` | 1 | `0x98` → `0x90` |
| 115 | `0x1A574` | `loader.bank` | 1 | `0x03` → `0x10` |
| 116 | `0x3DA1F` | `sprite.x` | 1 | `0xf8` → `0xef` |

## 附录 B：文本条目（121 条）

| id | section | 状态 | 译文 |
| --- | --- | --- | --- |
| `stage_1_number` | stage | integrated | 场景1 |
| `stage_1_name` | stage | integrated | 葛绿谷绿 |
| `stage_2_number` | stage | integrated | 场景2 |
| `stage_2_name` | stage | integrated | 箩箩箩的城堡 |
| `stage_3_number` | stage | integrated | 场景3 |
| `stage_3_name` | stage | integrated | 漂浮岛屿 |
| `stage_4_number` | stage | integrated | 场景4 |
| `stage_4_name` | stage | integrated | 泡泡云层 |
| `stage_5_number` | stage | integrated | 场景5 |
| `stage_5_name` | stage | integrated | 帝帝帝山 |
| `configuration` | menu | integrated | 配置 |
| `configuration_mode` | menu | integrated | 模式 |
| `vital` | menu | integrated | 体力： |
| `configuration_kirby` | menu | integrated | 卡比： |
| `configuration_sound` | menu | integrated | 声音 |
| `configuration_test` | menu | integrated | 测试 |
| `configuration_exit` | menu | integrated | 退出 |
| `sound_test` | menu | integrated | 声音测试 |
| `music` | menu | integrated | 音乐 |
| `sound` | menu | integrated | 音效 |
| `game_over` | menu | integrated | 游戏结束 |
| `continue` | menu | integrated | 继续 |
| `end` | menu | integrated | 结束 |
| `copyright_year` | copyright | not_localized | ©1992 |
| `copyright_hal` | copyright | not_localized | HAL LABORATORY,INC. |
| `copyright_nintendo` | copyright | not_localized | LICENSED TO NINTENDO |
| `title_menu_start` | title | not_localized | 开始游戏 |
| `title_menu_sound_test` | title | not_localized | 声音测试 |
| `extra_game` | title | integrated | 额外游戏 |
| `logo` | title | integrated | 星之卡比 |
| `hud_kirby` | hud | integrated | 卡比 |
| `hud_score` | hud | integrated | 积分 |
| `graphic_ending_01_01` | gallery | integrated | 黑刺球 |
| `graphic_ending_01_02` | gallery | integrated | 瓦豆鲁迪 |
| `graphic_ending_01_03` | gallery | integrated | 飞翅球球 |
| `graphic_ending_01_04` | gallery | integrated | 瓦豆鲁笃 |
| `graphic_ending_01_05` | gallery | integrated | 黑大炮 |
| `graphic_ending_02_01` | gallery | integrated | 喳喳鸟 |
| `graphic_ending_02_02` | gallery | integrated | 头带熊 |
| `graphic_ending_02_03` | gallery | integrated | 蘑菇怪 |
| `graphic_ending_02_04` | gallery | integrated | 小波比兄弟 |
| `graphic_ending_03_01` | gallery | integrated | 大波比兄弟 |
| `graphic_ending_03_02` | gallery | integrated | 风语大树 |
| `graphic_ending_04_01` | gallery | integrated | 振翅蝙蝠 |
| `graphic_ending_04_02` | gallery | integrated | 绿海葵 |
| `graphic_ending_04_03` | gallery | integrated | 芒比尸 |
| `graphic_ending_04_04` | gallery | integrated | 魔扫把 |
| `graphic_ending_04_05` | gallery | integrated | 两面派 |
| `graphic_ending_04_06` | gallery | integrated | 吐舌箱 |
| `graphic_ending_04_07` | gallery | integrated | 惊吓幽灵 |
| `graphic_ending_05_01` | gallery | integrated | 箩箩箩 |
| `graphic_ending_05_02` | gallery | integrated | 菈菈菈 |
| `graphic_ending_06_01` | gallery | integrated | 蛙镜鱼 |
| `graphic_ending_06_02` | gallery | integrated | 石像怪 |
| `graphic_ending_06_03` | gallery | integrated | 乌贼怪 |
| `graphic_ending_06_04` | gallery | integrated | 圆锥寄居蟹 |
| `graphic_ending_06_05` | gallery | integrated | 光束贝 |
| `graphic_ending_07_01` | gallery | integrated | 卡钸拉 |
| `graphic_ending_08_01` | gallery | integrated | 膨胀云 |
| `graphic_ending_08_02` | gallery | integrated | 疯狂鬼面 |
| `graphic_ending_08_03` | gallery | integrated | 尖耳怪 |
| `graphic_ending_08_04` | gallery | integrated | 晕晕怪 |
| `graphic_ending_08_05` | gallery | integrated | 弯刀骑士 |
| `graphic_ending_09_01` | gallery | integrated | 独眼云 |
| `graphic_ending_10_01` | gallery | integrated | 喔喔鸡 |
| `graphic_ending_10_02` | gallery | integrated | 振翅球球 |
| `graphic_ending_10_03` | gallery | integrated | 蛋糕怪 |
| `graphic_ending_11_01` | gallery | integrated | P瓜先生 |
| `graphic_ending_11_02` | gallery | integrated | 睡帽幽灵 |
| `graphic_ending_11_03` | gallery | integrated | 冒出箱 |
| `graphic_ending_11_04` | gallery | integrated | 骷髅头 |
| `graphic_ending_12_01` | gallery | integrated | 章鱼怪 |
| `graphic_ending_12_02` | gallery | integrated | 暴躁石像 |
| `graphic_ending_12_03` | gallery | integrated | 独眼蟹 |
| `graphic_ending_12_04` | gallery | integrated | 连射炮 |
| `graphic_ending_13_01` | gallery | integrated | 子弹鹈鹕 |
| `graphic_ending_13_02` | gallery | integrated | 胡须猫 |
| `graphic_ending_13_03` | gallery | integrated | 本尼 |
| `graphic_ending_13_04` | gallery | integrated | 武魔 |
| `graphic_ending_14_01` | gallery | integrated | 帝帝帝大王 |
| `jp_credits_01` | credits | not_localized | THE CREDITS |
| `jp_credits_04` | credits | not_localized | DIRECTOR |
| `jp_credits_05` | credits | not_localized | CHIEF DESIGNER |
| `jp_credits_06` | credits | not_localized | MASA SAKURAI |
| `jp_credits_08` | credits | not_localized | CHIEF PROGRAMMER |
| `jp_credits_10` | credits | not_localized | KYOUHEI MIYABI |
| `jp_credits_12` | credits | not_localized | PROGRAMMER |
| `jp_credits_14` | credits | not_localized | SUNDAY RAIN |
| `jp_credits_16` | credits | not_localized | GDV PROGRAMMER |
| `jp_credits_18` | credits | not_localized | MAMMY PRECO |
| `jp_credits_20` | credits | not_localized | GDV PROGRAMMER |
| `jp_credits_22` | credits | not_localized | TETSUYA NOTOYA |
| `jp_credits_24` | credits | not_localized | DESIGNER |
| `jp_credits_26` | credits | not_localized | MOGAMI KURAND |
| `jp_credits_28` | credits | not_localized | SOUND COMPOSER |
| `jp_credits_30` | credits | not_localized | JUN ISHIKAWA |
| `jp_credits_32` | credits | not_localized | SPECIAL THANKS |
| `jp_credits_34` | credits | not_localized | BUBBY |
| `jp_credits_36` | credits | not_localized | SPECIAL THANKS |
| `jp_credits_38` | credits | not_localized | CIPHER |
| `jp_credits_40` | credits | not_localized | SUPERVISOR |
| `jp_credits_42` | credits | not_localized | BOU NAKAJIMA |
| `jp_credits_44` | credits | not_localized | PRODUCER |
| `jp_credits_46` | credits | not_localized | MAKOTO KANAI |
| `jp_credits_48` | credits | not_localized | AND |
| `jp_credits_50` | credits | not_localized | SO MANY PLAYERS. |
| `jp_credits_52` | credits | not_localized | PRESENTED BY |
| `jp_credits_54` | credits | not_localized | HAL LABORATORY,INC. |
| `jp_credits_56` | credits | not_localized | LICENSED TO |
| `jp_credits_58` | credits | not_localized | NINTENDO |
| `jp_credits_60` | credits | not_localized | THANK YOU FOR |
| `jp_credits_62` | credits | not_localized | PLAYING. |
| `graphic_ending_15_01` | ending_hint | integrated | 配置⏎模式 |
| `graphic_ending_15_02` | ending_hint | integrated | 水平⏎真不错呢， |
| `graphic_ending_15_03` | ending_hint | integrated | 送你一份⏎特别的礼物♪ |
| `graphic_ending_15_04` | ending_hint | integrated | 感谢⏎您的游玩！ |
| `graphic_ending_16_01` | ending_hint | integrated | 额外⏎游戏 |
| `graphic_ending_16_02` | ending_hint | integrated | 恭喜⏎通关！ |
| `graphic_ending_16_03` | ending_hint | integrated | 在标题界面⏎输入左侧指令， |
| `graphic_ending_16_04` | ending_hint | integrated | 踏上⏎新的⏎冒险吧！ |
| `ending_sign_oshimai` | ending | integrated | 剧终 |

## 附录 C：页面层（30 页）

| id | 存储 | 角色 | 文件 | 用途 |
| --- | --- | --- | --- | --- |
| `rom_041000` | edit | active | `03_Image/edits/rom_041000.json` | 普通模式 HUD 字形条 |
| `rom_041103` | edit | active | `03_Image/edits/rom_041103.json` | 额外模式 HUD 字形条 |
| `rom_0438f6` | page | active | `03_Image/pages/rom_0438f6.png` | 声音测试页 |
| `rom_04454c` | page | active | `03_Image/pages/rom_04454c.png` | GAME OVER 画面 |
| `rom_044734` | page | active | `03_Image/pages/rom_044734.png` | CONTINUE 画面 |
| `rom_048462` | edit | active | `03_Image/edits/rom_048462.json` | 图鉴页·黑刺球等 + 蘑菇林 地图 |
| `rom_0496d4` | edit | active | `03_Image/edits/rom_0496d4.json` | 图鉴页·箩箩箩/菈菈菈 + 城堡 地图 |
| `rom_049bf8` | edit | active | `03_Image/edits/rom_049bf8.json` | 图鉴页·蛙镜鱼等 + 树林 地图 |
| `rom_04a3a1` | edit | active | `03_Image/edits/rom_04a3a1.json` | 图鉴页·疯狂鬼面等 + 城市 地图 |
| `rom_04ab1b` | edit | active | `03_Image/edits/rom_04ab1b.json` | 图鉴页·喔喔鸡等 + 树林 地图 |
| `rom_04b4db` | edit | active | `03_Image/edits/rom_04b4db.json` | 图鉴页·章鱼怪等 + 海与船 地图 |
| `rom_04b943` | edit | active | `03_Image/edits/rom_04b943.json` | 图鉴页·子弹鹈鹕等 + 星空 地图 |
| `rom_04c4f4` | edit | active | `03_Image/edits/rom_04c4f4.json` | 图鉴页·喳喳鸟等 + 山丘 地图 |
| `rom_04caf2` | edit | active | `03_Image/edits/rom_04caf2.json` | 图鉴页·振翅蝙蝠等 + 城堡 地图（蝙蝠页） |
| `rom_04cd98` | edit | active | `03_Image/edits/rom_04cd98.json` | 图鉴页·卡钸拉 + 云 地图 |
| `rom_04d0bb` | edit | active | `03_Image/edits/rom_04d0bb.json` | 图鉴页·独眼云 + 星空 地图 |
| `rom_04d586` | edit | active | `03_Image/edits/rom_04d586.json` | 图鉴页·睡帽幽灵等 + 砖墙 地图 |
| `rom_04d918` | edit | active | `03_Image/edits/rom_04d918.json` | 图鉴页·帝帝帝大王 + 王冠舞台 地图 |
| `rom_050000` | edit | active | `03_Image/edits/rom_050000.json` | 结局/通关提示精灵表（剧终牌等） |
| `rom_055050` | edit | active | `03_Image/edits/rom_055050.json` | 普通模式通关提示（提示如何进入额外模式） 地图 |
| `rom_056110` | edit | active | `03_Image/edits/rom_056110.json` | 额外模式通关提示（提示如何进入配置模式） 地图 |
| `rom_058000` | edit | active | `03_Image/edits/rom_058000.json` | 关卡介绍右下角 32×16 中文角标（开场装饰） |
| `rom_05c000` | page | active | `03_Image/pages/rom_05c000.png` | 配置页整包（256 图块 + 地图） |
| `rom_06c000` | page | active | `03_Image/pages/rom_06c000.png` | 场景 1 介绍整包（128 图块 + 地图） |
| `rom_06c70b` | page | active | `03_Image/pages/rom_06c70b.png` | 场景 2 介绍整包 |
| `rom_06cda8` | page | active | `03_Image/pages/rom_06cda8.png` | 场景 3 介绍整包 |
| `rom_06d490` | page | active | `03_Image/pages/rom_06d490.png` | 场景 4 介绍整包 |
| `rom_06db85` | page | active | `03_Image/pages/rom_06db85.png` | 场景 5 介绍整包（240 px 高） |
| `rom_070000` | page | active | `03_Image/pages/rom_070000.png` | 标题画面整包（中文 Logo + 额外游戏 + 菜单） |
| `rom_0742b3` | edit | active | `03_Image/edits/rom_0742b3.json` | 图鉴第 3 页·大波比兄弟/风语大树 地图 |
