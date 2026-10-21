# 视觉回归包 → 页面源核对

由 `PYTHONPATH=build/pylibs python 00_Tools/audit_visual_regression.py --write` 生成。

包由 `00_Tools/capture_pages.py` 从 `baserom.gb` 单独重建，不依赖外部模拟器存档。

- 包内 ROM SHA-256：`bb754e254945009d2569ae47cd47c21c714cb59ad0cd005fbfa8348deb93f635`（与当前构建一致）
- 模拟器：PyBoy；画面数：33；缺失画面：无
- 原生重载校验：未记录；屏幕/内存/退出状态一致：未记录
- 包内逐像素核验：不适用（PyBoy 截图直接取自模拟器帧缓冲，无需从 VRAM/OAM/IO 反推重建）
- 页面覆盖：30/30 个活跃页面被此包覆盖；缺失：无

## 逐屏核对

| 画面 | 说明 | 期望页面 | 地图匹配 | tile 匹配 | 地图来源 | 动态差异 | 状态 |
| --- | --- | --- | ---: | ---: | --- | ---: | --- |
| `configuration` | 配置页 | `rom_05c000` | 0.984 | 1.000 | bgmap | 9 | PASS_DYNAMIC |
| `continue` | CONTINUE / END | `rom_044734` | 1.000 | 1.000 | bgmap | - | PASS |
| `credits_bonus` | 演职人员表（附加） | - | - | - | - | - | NOT_LOCALIZED |
| `ending_sign` | 剧终牌 | `rom_050000` | 0.000 | 1.000 | - | - | PASS |
| `gallery_01` | 图鉴第 1 页 | `rom_048462` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_02` | 图鉴第 2 页 | `rom_04c4f4` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_03` | 图鉴第 3 页 | `rom_0742b3` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_04` | 图鉴第 4 页 | `rom_04caf2` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_05` | 图鉴第 5 页 | `rom_0496d4` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_06` | 图鉴第 6 页 | `rom_049bf8` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_07` | 图鉴第 7 页 | `rom_04cd98` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_08` | 图鉴第 8 页 | `rom_04a3a1` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_09` | 图鉴第 9 页 | `rom_04d0bb` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_10` | 图鉴第 10 页 | `rom_04ab1b` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_11` | 图鉴第 11 页 | `rom_04d586` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_12` | 图鉴第 12 页 | `rom_04b4db` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_13` | 图鉴第 13 页 | `rom_04b943` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_14` | 图鉴第 14 页 | `rom_04d918` | 1.000 | 1.000 | bgmap | - | PASS |
| `game_over` | GAME OVER | `rom_04454c` | 1.000 | 1.000 | bgmap | - | PASS |
| `hint_extra` | 通关提示页（额外模式） | `rom_056110` | 1.000 | 1.000 | bgmap | - | PASS |
| `hint_normal` | 通关提示页（普通模式） | `rom_055050` | 1.000 | 1.000 | bgmap | - | PASS |
| `hud_extra` | 游戏内 HUD（额外模式） | `rom_041103` | 0.000 | 1.000 | - | - | PASS |
| `hud_normal` | 游戏内 HUD（普通模式） | `rom_041000` | 0.000 | 1.000 | - | - | PASS |
| `main_menu` | 主界面（额外游戏） | `rom_070000` | 1.000 | 1.000 | bgmap | - | PASS |
| `sound_test` | 声音测试 | `rom_0438f6` | 0.998 | 1.000 | bgmap | 1 | PASS_DYNAMIC |
| `stage_1_intro` | 场景 1 介绍 | `rom_06c000` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_2_intro` | 场景 2 介绍 | `rom_06c70b` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_3_intro` | 场景 3 介绍 | `rom_06cda8` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_4_intro` | 场景 4 介绍 | `rom_06d490` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_5_intro` | 场景 5 介绍 | `rom_06db85` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_5_intro_scrolled` | 场景 5 介绍（滚动后） | - | - | - | - | - | NOT_LOCALIZED |
| `title` | 标题 | `rom_070000` | 1.000 | 1.000 | bgmap | - | PASS |
| `title_animation` | 标题（动画） | - | - | - | - | - | NOT_LOCALIZED |
| `<shared:rom_058000>` | 共享图块流（由 `stage_1_intro` 的捕获覆盖） | `rom_058000` | 0.000 | 1.000 | - | - | PASS |

## 问题

- 无。

## 说明

- 地图匹配取 `bgmap.bin`、VRAM `0x9800`、VRAM `0x9C00` 三个来源中的最佳值；标题页允许纵向滚动偏移。
- tile 匹配：bundle 页优先按该页 loader 目的地址比较，其次在 VRAM 中搜索该页 tile 块；tilemap 页搜索 tileset 前缀；sheet 页搜索完整图块块。
- `credits_bonus` 是未汉化的原版演职人员表滚动画面，不对应任何本地化页面，包内也标记为动态（非静态逐像素核验）。
- `configuration` / `sound_test` 的地图差异是菜单光标/选项高亮在页面加载后写入 BG map 造成的动态格子，tile 块仍精确匹配，因此标为 `PASS_DYNAMIC`。
- `hint_normal` 是普通模式通关后的提示页（提示如何进入额外模式），对应 `rom_055050`；`hint_extra` 是额外模式通关后的提示页（提示如何进入配置模式），对应 `rom_056110`。`change_surface.json` 的 purpose 已按此修正。
- `title` 与 `main_menu` 都是 `rom_070000`；`intro_decoration`（`rom_058000`）是场景 1-4 介绍与 CONTINUE 共用的 0x8800 图块流，不是独立画面，因此不单独截图，而是用 `stage_1_intro` 的捕获（`<shared:rom_058000>` 行）核对。
- sheet 页（HUD/角标/剧终牌）没有独立的 BG map 可比较，只看整块 tile 是否出现在 VRAM。
- 本报告只核对包的外观数据与页面源；包由 `capture_pages.py` 重建，不随仓库分发任何模拟器存档或 ROM。
