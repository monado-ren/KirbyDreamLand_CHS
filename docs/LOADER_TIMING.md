# 装载器成本（静态审计）

由 `python 00_Tools/audit_loader_timing.py --write` 从 `baserom.gb` + 符号层生成。
数字是 HAL 解压后的字节数；游戏每帧约搬 28 个图块（16 字节），因此字节增长
可换算为装载帧数增长。**这不是模拟器实测**，但足以说明为什么汉化版的
帧号不能按固定偏移对齐（TAS/逐帧截图）。

```text
LOADERS=41 COMPARED=41 ORIGINAL=66720 LOCALIZED=81056 DELTA=+14336 (21%) GROWN=5
```

## 变大的装载器

| site | 资源 | 原版 bank:地址 | 原版 decoded | 汉化 decoded | 增量 |
| --- | --- | --- | ---: | ---: | ---: |
| `configuration_map_full_bundle_load` | `rom_05c000` | 3:`0x453A` | 576 | 4672 | **+4096** |
| `title_bundle_load` | `rom_070000` | 3:`0x4000` | 1152 | 5248 | **+4096** |
| `continue_map_load` | `rom_044734` | 3:`0x4666` | 576 | 2624 | **+2048** |
| `gameover_map_load` | `rom_04454c` | 3:`0x4616` | 576 | 2624 | **+2048** |
| `sound_test_map_load` | `rom_0438f6` | 3:`0x44C2` | 576 | 2624 | **+2048** |

## 未变的装载器

| site | 资源 | decoded |
| --- | --- | ---: |
| `ending_034000_load` | `rom_048000` | 2048 |
| `ending_0345c0_load` | `rom_048462` | 1024 |
| `ending_0346fb_load` | `rom_04c000` | 2048 |
| `ending_034cb4_load` | `rom_04c4f4` | 1024 |
| `ending_034dc0_load` | `rom_074000` | 2048 |
| `ending_03535c_load` | `rom_0742b3` | 1024 |
| `ending_03543e_load` | `rom_04c609` | 2048 |
| `ending_035987_load` | `rom_04caf2` | 1024 |
| `ending_035a89_load` | `rom_04954a` | 2048 |
| `ending_035fd2_load` | `rom_0496d4` | 1024 |
| `ending_036063_load` | `rom_049769` | 2048 |
| `ending_036553_load` | `rom_049bf8` | 1024 |
| `ending_036658_load` | `rom_04cc04` | 2048 |
| `ending_036b80_load` | `rom_04cd98` | 1024 |
| `ending_036c7c_load` | `rom_049f9a` | 2048 |
| `ending_03717d_load` | `rom_04a3a1` | 1024 |
| `ending_03729b_load` | `rom_04ce8c` | 2048 |
| `ending_03779c_load` | `rom_04d0bb` | 1024 |
| `ending_0378cc_load` | `rom_04ab1b` | 1024 |
| `ending_038000_load` | `rom_04a7e9` | 2048 |
| `ending_038582_load` | `rom_04d1b8` | 2048 |
| `ending_038ac6_load` | `rom_04d586` | 1024 |
| `ending_038bf3_load` | `rom_04b11e` | 2048 |
| `ending_03911e_load` | `rom_04b4db` | 1024 |
| `ending_039206_load` | `rom_04b5dd` | 2048 |
| `ending_039707_load` | `rom_04b943` | 1024 |
| `ending_039820_load` | `rom_04d6b7` | 2048 |
| `ending_039be1_load` | `rom_04d918` | 1024 |
| `ending_039cbf_load_pointer` | `rom_055130` | 6144 |
| `ending_03acec_load_pointer` | `rom_056110` | 1024 |
| `ending_03adda_load_pointer` | `rom_054000` | 6144 |
| `ending_03be31_load_pointer` | `rom_055050` | 1024 |
| `ending_sprites_load` | `rom_050000` | 3584 |
| `extra_hud_load` | `rom_041103` | 400 |
| `intro_decoration_load` | `rom_058000` | 1536 |
| `normal_hud_load` | `rom_041000` | 400 |

## 说明

- 原版载荷位置由未打补丁的 loader 操作数（bank + 源地址）确定；
- 汉化载荷大小取 `04_Data/manifest.json` 的 `decoded_size`；
- 标题/配置/失败页从 0x9800 改到 0x8800/0x9000 后，整包携带了更多图块，
  这是字节增长的来源；代码本身没有变慢（VBlank 补丁与装载循环无关）。


## 删除死装载后的实际成本（v0.5.2）

标题页与配置页的整包会完全覆盖同一段代码里前面几次装载的 VRAM 区间，
因此那 6 次 `CALL $20C1` 已改为 NOP（详见 `DEAD_LOADS.md`）。上表列的是
“装载器设计载荷”；实际执行的字节数要扣除这些看不到结果的装载：

| | 原版 | v0.5.1 | v0.5.2 |
| --- | ---: | ---: | ---: |
| 实际解压字节 | 66,720 | 81,056 | **75,024** |
| 相对原版 | — | +14,336（+21%） | **+8,304（+12%）** |
| 折合帧数（约 585 B/帧） | — | +24.5 | **+14.2** |

省下的 6,032 字节（约 10.3 帧）来自被整包覆盖的死装载，与中文内容无关。
剩下的增量是中文图块复杂度的固有成本，不改图无法消除。

