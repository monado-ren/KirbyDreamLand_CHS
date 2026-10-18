# 页面 VRAM / tile / 地图预算审计

由 `python 00_Tools/audit_pages.py --write` 生成；静态审计，不运行 ROM。

## 汇总

- 页面：48（当前装载 30，历史副本 18）；整页 bundle：21；基线+覆盖层页：27
- 当前装载的活跃资源：46
- 零 packed 余量资源：19（`capacity == packed_size`）
- 硬错误：0；警告：9
- 全机 VRAM 8 KiB = 384 个 8×8 tile；BG 地图 32×32、每格 8 bit（最多 256 种 tile 编号）

## 页面表

| 页面 | 状态 | 类型 | tile 数 | 地图格/唯一码/最大码 | 外部基线码 | 装载目的 | tile块后地图落点 | decoded | packed/cap | 余量 |
| --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | --- | ---: |
| `rom_0438f6` | active | bundle | 128 | 576/58/0xC7 | 68 | 0x9000 | 0x9800 | 2624 | 713/1802 | 1089 |
| `rom_04454c` | active | bundle | 128 | 576/21/0x7F | 0 | 0x9000 | 0x9800 | 2624 | 488/488 | 0 |
| `rom_044734` | active | bundle | 128 | 576/18/0xFE | 216 | 0x9000 | 0x9800 | 2624 | 478/14540 | 14062 |
| `rom_05c000` | active | bundle | 256 | 576/125/0xFE | 0 | 0x8800 | 0x9800 | 4672 | 2559/16384 | 13825 |
| `rom_06c000` | active | bundle | 128 | 576/61/0xD9 | 8 | - | - | 2624 | 1803/1803 | 0 |
| `rom_06c70b` | active | bundle | 128 | 576/65/0xD9 | 8 | - | - | 2624 | 1693/1693 | 0 |
| `rom_06cda8` | active | bundle | 128 | 576/62/0xD9 | 224 | - | - | 2624 | 1768/1768 | 0 |
| `rom_06d490` | active | bundle | 128 | 576/50/0xD9 | 224 | - | - | 2624 | 1781/1781 | 0 |
| `rom_06db85` | active | bundle | 128 | 960/28/0xFC | 32 | - | - | 3008 | 1668/9339 | 7671 |
| `rom_070000` | active | bundle | 292 | 576/21/0xFE | 0 | 0x8800 | 0x9A40 | 5248 | 3186/16384 | 13198 |
| `rom_041000` | active | edit | 25 | - | - | - | - | 400 | 259/259 | 0 |
| `rom_041103` | active | edit | 25 | - | - | - | - | 400 | 259/259 | 0 |
| `rom_048462` | active | edit | 128 | 1024/87/0x7F | 0 | - | - | 1024 | 335/335 | 0 |
| `rom_0496d4` | active | edit | 128 | 1024/32/0x7F | 0 | - | - | 1024 | 149/149 | 0 |
| `rom_049bf8` | active | edit | 128 | 1024/95/0x7F | 0 | - | - | 1024 | 285/285 | 0 |
| `rom_04a3a1` | active | edit | 128 | 1024/86/0x7F | 0 | - | - | 1024 | 293/293 | 0 |
| `rom_04ab1b` | active | edit | 128 | 1024/61/0x7F | 0 | - | - | 1024 | 264/264 | 0 |
| `rom_04b4db` | active | edit | 128 | 1024/79/0x7F | 0 | - | - | 1024 | 258/258 | 0 |
| `rom_04b943` | active | edit | 128 | 1024/71/0x7F | 0 | - | - | 1024 | 306/306 | 0 |
| `rom_04c4f4` | active | edit | 128 | 1024/98/0x7F | 0 | - | - | 1024 | 277/277 | 0 |
| `rom_04caf2` | active | edit | 128 | 1024/106/0x7F | 0 | - | - | 1024 | 274/274 | 0 |
| `rom_04cd98` | active | edit | 128 | 1024/37/0x7F | 0 | - | - | 1024 | 244/244 | 0 |
| `rom_04d0bb` | active | edit | 128 | 1024/43/0x7F | 0 | - | - | 1024 | 253/253 | 0 |
| `rom_04d586` | active | edit | 128 | 1024/78/0x7F | 0 | - | - | 1024 | 305/305 | 0 |
| `rom_04d918` | active | edit | 128 | 1024/49/0x7F | 0 | - | - | 1024 | 164/9960 | 9796 |
| `rom_050000` | active | edit | 224 | - | - | - | - | 3584 | 2418/16384 | 13966 |
| `rom_055050` | active | edit | 384 | 1024/100/0x7F | - | - | - | 1024 | 223/224 | 1 |
| `rom_056110` | active | edit | 384 | 1024/94/0x7F | - | - | - | 1024 | 215/7920 | 7705 |
| `rom_058000` | active | edit | 96 | - | - | - | - | 1536 | 1268/16384 | 15116 |
| `rom_0742b3` | active | edit | 128 | 1024/53/0x7F | 0 | - | - | 1024 | 231/15693 | 15462 |
| `rom_040000` | legacy | bundle | 292 | 576/21/0xFE | 0 | - | - | 5248 | 3057/4096 | 1039 |
| `rom_041206` | legacy | bundle | 128 | 576/60/0xF5 | 9 | - | - | 2624 | 1799/1799 | 0 |
| `rom_04190d` | legacy | bundle | 128 | 576/65/0xFA | 9 | - | - | 2624 | 1675/1675 | 0 |
| `rom_041f98` | legacy | bundle | 128 | 576/62/0xFB | 225 | - | - | 2624 | 1749/1749 | 0 |
| `rom_04266d` | legacy | bundle | 128 | 576/50/0xFC | 225 | - | - | 2624 | 1776/1776 | 0 |
| `rom_042d5d` | legacy | bundle | 128 | 960/28/0xFC | 33 | - | - | 3008 | 1640/1640 | 0 |
| `rom_0433c5` | legacy | bundle | 128 | 576/98/0xFE | 482 | - | - | 2624 | 1329/1329 | 0 |
| `rom_044000` | legacy | bundle | 128 | 576/95/0xFE | 505 | - | - | 2624 | 1356/1356 | 0 |
| `rom_060000` | legacy | bundle | 292 | 576/21/0xFE | 0 | - | - | 5248 | 3186/16384 | 13198 |
| `rom_064000` | legacy | bundle | 128 | 576/62/0xF5 | 9 | - | - | 2624 | 1786/1786 | 0 |
| `rom_0646fa` | legacy | bundle | 128 | 576/65/0xFA | 9 | - | - | 2624 | 1673/14598 | 12925 |
| `rom_048ab2` | legacy | edit | 128 | 1024/98/0x7F | 0 | - | - | 1024 | 275/275 | 0 |
| `rom_048e5c` | legacy | edit | 128 | 1024/53/0x7F | 0 | - | - | 1024 | 238/238 | 0 |
| `rom_049433` | legacy | edit | 128 | 1024/106/0x7F | 0 | - | - | 1024 | 279/279 | 0 |
| `rom_049eaf` | legacy | edit | 128 | 1024/34/0x7F | 0 | - | - | 1024 | 235/235 | 0 |
| `rom_04a6f0` | legacy | edit | 128 | 1024/43/0x7F | 0 | - | - | 1024 | 249/249 | 0 |
| `rom_04afee` | legacy | edit | 128 | 1024/78/0x7F | 0 | - | - | 1024 | 304/304 | 0 |
| `rom_04bcd1` | legacy | edit | 128 | 1024/49/0x7F | 0 | - | - | 1024 | 164/815 | 651 |

## 装载点

| 页面 | 装载点 | 声明 VRAM 目的 | 说明 |
| --- | --- | --- | --- |
| `rom_041000` | `normal_hud_load` | - | 普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节） |
| `rom_041103` | `extra_hud_load` | - | 额外 HUD 图块装载点（重复 2 处） |
| `rom_070000` | `title_bundle_load` | 0x8800 | 标题整包装载：源 bank 3→28，VRAM 目的 0x9800→0x8800 |
| `rom_058000` | `intro_decoration_load` | - | 开场装饰图块装载点（重复 2 处） |
| `rom_04454c` | `gameover_map_load` | 0x9000 | GAME OVER 整包装载（VRAM 目的 0x9800→0x9000） |
| `rom_044734` | `continue_map_load` | 0x9000 | CONTINUE 整包装载（VRAM 目的 0x9800→0x9000） |
| `rom_050000` | `ending_sprites_load` | - | 结局精灵表装载点（重复 2 处） |
| `rom_048000` | `ending_034000_load` | - | 图鉴页装载点（bank）：图鉴页·黑刺球等 + 蘑菇林 图块集 |
| `rom_048462` | `ending_0345c0_load` | - | 图鉴页装载点（bank）：图鉴页·黑刺球等 + 蘑菇林 地图 |
| `rom_04c000` | `ending_0346fb_load` | - | 图鉴页装载点（bank）：图鉴页·喳喳鸟等 + 山丘 图块集 |
| `rom_04c4f4` | `ending_034cb4_load` | - | 图鉴页装载点（bank）：图鉴页·喳喳鸟等 + 山丘 地图 |
| `rom_074000` | `ending_034dc0_load` | - | 图鉴页装载点（bank）：图鉴第 3 页·大波比兄弟/风语大树 图块集 |
| `rom_0742b3` | `ending_03535c_load` | - | 图鉴页装载点（bank）：图鉴第 3 页·大波比兄弟/风语大树 地图 |
| `rom_04c609` | `ending_03543e_load` | - | 图鉴页装载点（bank）：图鉴页·振翅蝙蝠等 + 城堡 图块集 |
| `rom_04caf2` | `ending_035987_load` | - | 图鉴页装载点（bank）：图鉴页·振翅蝙蝠等 + 城堡 地图（蝙蝠页） |
| `rom_04954a` | `ending_035a89_load` | - | 图鉴页装载点（bank）：图鉴页·箩箩箩/菈菈菈 + 城堡 图块集 |
| `rom_0496d4` | `ending_035fd2_load` | - | 图鉴页装载点（bank）：图鉴页·箩箩箩/菈菈菈 + 城堡 地图 |
| `rom_049769` | `ending_036063_load` | - | 图鉴页装载点（bank）：图鉴页·蛙镜鱼等 + 树林 图块集 |
| `rom_049bf8` | `ending_036553_load` | - | 图鉴页装载点（bank）：图鉴页·蛙镜鱼等 + 树林 地图 |
| `rom_04cc04` | `ending_036658_load` | - | 图鉴页装载点（bank）：图鉴页·卡钸拉 + 云 图块集 |
| `rom_04cd98` | `ending_036b80_load` | - | 图鉴页装载点（bank）：图鉴页·卡钸拉 + 云 地图 |
| `rom_049f9a` | `ending_036c7c_load` | - | 图鉴页装载点（bank）：图鉴页·疯狂鬼面等 + 城市 图块集 |
| `rom_04a3a1` | `ending_03717d_load` | - | 图鉴页装载点（bank）：图鉴页·疯狂鬼面等 + 城市 地图 |
| `rom_04ce8c` | `ending_03729b_load` | - | 图鉴页装载点（bank）：图鉴页·独眼云 + 星空 图块集 |
| `rom_04d0bb` | `ending_03779c_load` | - | 图鉴页装载点（bank）：图鉴页·独眼云 + 星空 地图 |
| `rom_04a7e9` | `ending_038000_load` | - | 图鉴页装载点（bank）：图鉴页·喔喔鸡等 + 树林 图块集 |
| `rom_04ab1b` | `ending_0378cc_load` | - | 图鉴页装载点（bank）：图鉴页·喔喔鸡等 + 树林 地图 |
| `rom_04d1b8` | `ending_038582_load` | - | 图鉴页装载点（bank）：图鉴页·睡帽幽灵等 + 砖墙 图块集 |
| `rom_04d586` | `ending_038ac6_load` | - | 图鉴页装载点（bank）：图鉴页·睡帽幽灵等 + 砖墙 地图 |
| `rom_04b11e` | `ending_038bf3_load` | - | 图鉴页装载点（bank）：图鉴页·章鱼怪等 + 海与船 图块集 |
| `rom_04b4db` | `ending_03911e_load` | - | 图鉴页装载点（bank）：图鉴页·章鱼怪等 + 海与船 地图 |
| `rom_04b5dd` | `ending_039206_load` | - | 图鉴页装载点（bank）：图鉴页·子弹鹈鹕等 + 星空 图块集 |
| `rom_04b943` | `ending_039707_load` | - | 图鉴页装载点（bank）：图鉴页·子弹鹈鹕等 + 星空 地图 |
| `rom_04d6b7` | `ending_039820_load` | - | 图鉴页装载点（bank）：图鉴页·帝帝帝大王 + 王冠舞台 图块集 |
| `rom_04d918` | `ending_039be1_load` | - | 图鉴页装载点（bank）：图鉴页·帝帝帝大王 + 王冠舞台 地图 |
| `rom_055130` | `ending_039cbf_load_pointer` | - | 图鉴/提示页装载指针（地址+bank）：额外模式通关提示 图块集（整屏 384 图块） |
| `rom_056110` | `ending_03acec_load_pointer` | - | 图鉴/提示页装载指针（地址+bank）：额外模式通关提示 地图 |
| `rom_054000` | `ending_03adda_load_pointer` | - | 图鉴/提示页装载指针（地址+bank）：普通模式通关提示 图块集（整屏 384 图块） |
| `rom_055050` | `ending_03be31_load_pointer` | - | 图鉴/提示页装载指针（地址+bank）：普通模式通关提示 地图 |
| `rom_05c000` | `configuration_map_full_bundle_load` | 0x8800 | 配置整包装载：源 bank 3→23，VRAM 目的 0x9800→0x8800 |
| `rom_0438f6` | `sound_test_map_load` | 0x9000 | 声音测试整包装载（VRAM 目的 0x9800→0x9000） |

## 警告与限制

- rom_0438f6: 68 map cells reference baseline VRAM tiles (code >= 128)
- rom_044734: 216 map cells reference baseline VRAM tiles (code >= 128)
- rom_06c000: 8 map cells reference baseline VRAM tiles (code >= 128)
- rom_06c70b: 8 map cells reference baseline VRAM tiles (code >= 128)
- rom_06cda8: 224 map cells reference baseline VRAM tiles (code >= 128)
- rom_06d490: 224 map cells reference baseline VRAM tiles (code >= 128)
- rom_06db85: 32 map cells reference baseline VRAM tiles (code >= 128)
- rom_070000: tile block ends at 0x9A40, not BG map 0x9800
- rom_070000: 292 tiles exceed one 256-tile BG block

说明：

- “外部基线码”表示地图引用了本页 tile 块之外的 VRAM 图块（通常是原版关卡/图鉴共用图块），不算错误，但换页/扩页时要保证这些基线图块确实已被装载。
- “tile块后地图落点”按 `VRAM目的 + tile数×16` 估算；不等于 0x9800 的页面（如标题页）使用自己的分段装载方式，必须逐页人工/模拟器确认，不能按单一连续块理解。
- 加载时序（LCD off / VBlank）无法仅从 manifest 静态证明；扩页或改 loader 长度后必须重新验证。
- 本审计不做实机验证；字节级构建 PASS 只保证 ROM 与既有发布一致。
