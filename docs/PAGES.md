# 可读页面索引（03_Image/pages + 03_Image/edits）

运行时页面核对见 [`VISUAL_REGRESSION_AUDIT.md`](VISUAL_REGRESSION_AUDIT.md)（外部 BGB 视觉回归包，30/30 活跃页面覆盖）。

`03_Image/pages/` 与 `03_Image/edits/` 下共有 **48 个页面**，分两种存储方式：

| 存储 | 数量 | 路径 | 说明 |
| --- | --- | --- | --- |
| 基线+覆盖层（edit） | **27** | `03_Image/edits/<id>.json` + `03_Image/edits/<id>_cells.png` | 页面 = 用户自备 Rev1 ROM 的原始图块/地图（基线）+ 改动格子（覆盖层）。仓库不存原版美术，只存改动；用 `python 00_Tools/page_edits.py render` 在 gitignored 的 `build/pages/` 重建整页。 |
| 整页 PNG（bundle） | **21** | `03_Image/pages/<id>.png` | 关卡介绍、标题、配置、声音测试、GAME OVER、CONTINUE：单资源=图块+地图，整页图直接可读可编辑。 |

编辑流程：
```sh
python 00_Tools/pages.py render                 # 整页 PNG 写到 03_Image/pages，edit 页重建到 build/pages
# 编辑 build/pages/<id>.png 后：
python 00_Tools/pages.py retile build/pages/<id>.png   # 回写图块集/地图，并刷新 03_Image/edits 覆盖层
python 00_Tools/pages.py render --check         # 两种页面都与 03_Image/graphics 一致
python 00_Tools/page_edits.py check             # 覆盖层+基线 == 由 graphics 渲染的页面（需要 baserom.gb）
```

`03_Image/edits/<id>.json` 记录基线来源（Rev1 bank/CPU）、页面尺寸、改动格子索引与覆盖层图集；bundle 页面中引用原始 ROM 图块而无法归属本资源的格子仍显示为占位图案、retile 时只读。

## 基线+覆盖层页（27 张）

| 页面 | 尺寸 | id | 内容 |
| --- | --- | --- | --- |
| [edit](../03_Image/edits/rom_041000.json) · [cells](../03_Image/edits/rom_041000_cells.png) | 128×16 | `rom_041000` | 普通模式 HUD 字形条 |
| [edit](../03_Image/edits/rom_041103.json) · [cells](../03_Image/edits/rom_041103_cells.png) | 128×16 | `rom_041103` | 额外模式 HUD 字形条 |
| [edit](../03_Image/edits/rom_048462.json) · [cells](../03_Image/edits/rom_048462_cells.png) | 256×256 | `rom_048462` | 图鉴页·黑刺球等 + 蘑菇林 地图 |
| [edit](../03_Image/edits/rom_048ab2.json) · [cells](../03_Image/edits/rom_048ab2_cells.png) | 256×256 | `rom_048ab2` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_048e5c.json) · [cells](../03_Image/edits/rom_048e5c_cells.png) | 256×256 | `rom_048e5c` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_049433.json) · [cells](../03_Image/edits/rom_049433_cells.png) | 256×256 | `rom_049433` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_0496d4.json) · [cells](../03_Image/edits/rom_0496d4_cells.png) | 256×256 | `rom_0496d4` | 图鉴页·箩箩箩/菈菈菈 + 城堡 地图 |
| [edit](../03_Image/edits/rom_049bf8.json) · [cells](../03_Image/edits/rom_049bf8_cells.png) | 256×256 | `rom_049bf8` | 图鉴页·蛙镜鱼等 + 树林 地图 |
| [edit](../03_Image/edits/rom_049eaf.json) · [cells](../03_Image/edits/rom_049eaf_cells.png) | 256×256 | `rom_049eaf` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_04a3a1.json) · [cells](../03_Image/edits/rom_04a3a1_cells.png) | 256×256 | `rom_04a3a1` | 图鉴页·疯狂鬼面等 + 城市 地图 |
| [edit](../03_Image/edits/rom_04a6f0.json) · [cells](../03_Image/edits/rom_04a6f0_cells.png) | 256×256 | `rom_04a6f0` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_04ab1b.json) · [cells](../03_Image/edits/rom_04ab1b_cells.png) | 256×256 | `rom_04ab1b` | 图鉴页·喔喔鸡等 + 树林 地图 |
| [edit](../03_Image/edits/rom_04afee.json) · [cells](../03_Image/edits/rom_04afee_cells.png) | 256×256 | `rom_04afee` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_04b4db.json) · [cells](../03_Image/edits/rom_04b4db_cells.png) | 256×256 | `rom_04b4db` | 图鉴页·章鱼怪等 + 海与船 地图 |
| [edit](../03_Image/edits/rom_04b943.json) · [cells](../03_Image/edits/rom_04b943_cells.png) | 256×256 | `rom_04b943` | 图鉴页·子弹鹈鹕等 + 星空 地图 |
| [edit](../03_Image/edits/rom_04bcd1.json) · [cells](../03_Image/edits/rom_04bcd1_cells.png) | 256×256 | `rom_04bcd1` | 图鉴早期版本（历史副本） |
| [edit](../03_Image/edits/rom_04c4f4.json) · [cells](../03_Image/edits/rom_04c4f4_cells.png) | 256×256 | `rom_04c4f4` | 图鉴页·喳喳鸟等 + 山丘 地图 |
| [edit](../03_Image/edits/rom_04caf2.json) · [cells](../03_Image/edits/rom_04caf2_cells.png) | 256×256 | `rom_04caf2` | 图鉴页·振翅蝙蝠等 + 城堡 地图（蝙蝠页） |
| [edit](../03_Image/edits/rom_04cd98.json) · [cells](../03_Image/edits/rom_04cd98_cells.png) | 256×256 | `rom_04cd98` | 图鉴页·卡钸拉 + 云 地图 |
| [edit](../03_Image/edits/rom_04d0bb.json) · [cells](../03_Image/edits/rom_04d0bb_cells.png) | 256×256 | `rom_04d0bb` | 图鉴页·独眼云 + 星空 地图 |
| [edit](../03_Image/edits/rom_04d586.json) · [cells](../03_Image/edits/rom_04d586_cells.png) | 256×256 | `rom_04d586` | 图鉴页·睡帽幽灵等 + 砖墙 地图 |
| [edit](../03_Image/edits/rom_04d918.json) · [cells](../03_Image/edits/rom_04d918_cells.png) | 256×256 | `rom_04d918` | 图鉴页·帝帝帝大王 + 王冠舞台 地图 |
| [edit](../03_Image/edits/rom_050000.json) · [cells](../03_Image/edits/rom_050000_cells.png) | 128×112 | `rom_050000` | 结局/通关提示精灵表（剧终牌等） |
| [edit](../03_Image/edits/rom_055050.json) · [cells](../03_Image/edits/rom_055050_cells.png) | 256×256 | `rom_055050` | 普通模式通关提示（提示进入额外模式） 地图 |
| [edit](../03_Image/edits/rom_056110.json) · [cells](../03_Image/edits/rom_056110_cells.png) | 256×256 | `rom_056110` | 额外模式通关提示（提示进入配置模式） 地图 |
| [edit](../03_Image/edits/rom_058000.json) · [cells](../03_Image/edits/rom_058000_cells.png) | 128×48 | `rom_058000` | 关卡介绍右下角 32×16 中文角标（开场装饰） |
| [edit](../03_Image/edits/rom_0742b3.json) · [cells](../03_Image/edits/rom_0742b3_cells.png) | 256×256 | `rom_0742b3` | 图鉴第 3 页·大波比兄弟/风语大树 地图 |

## 整页 PNG 页（21 张）

| 页面 | 尺寸 | id | 内容 |
| --- | --- | --- | --- |
| [rom_040000.png](../03_Image/pages/rom_040000.png) | 256×144 | `rom_040000` | 标题画面·初版整包（历史副本） |
| [rom_041206.png](../03_Image/pages/rom_041206.png) | 256×144 | `rom_041206` | 场景 1 介绍·初版地图流（历史副本） |
| [rom_04190d.png](../03_Image/pages/rom_04190d.png) | 256×144 | `rom_04190d` | 场景 2 介绍·初版地图流（历史副本） |
| [rom_041f98.png](../03_Image/pages/rom_041f98.png) | 256×144 | `rom_041f98` | 场景 3 介绍·初版地图流（历史副本） |
| [rom_04266d.png](../03_Image/pages/rom_04266d.png) | 256×144 | `rom_04266d` | 场景 4 介绍·初版地图流（历史副本） |
| [rom_042d5d.png](../03_Image/pages/rom_042d5d.png) | 256×240 | `rom_042d5d` | 场景 5 介绍·初版地图流（历史副本） |
| [rom_0433c5.png](../03_Image/pages/rom_0433c5.png) | 256×144 | `rom_0433c5` | 配置页·初版地图（历史副本） |
| [rom_0438f6.png](../03_Image/pages/rom_0438f6.png) | 256×144 | `rom_0438f6` | 声音测试页 |
| [rom_044000.png](../03_Image/pages/rom_044000.png) | 256×144 | `rom_044000` | 配置页·初版地图（历史副本） |
| [rom_04454c.png](../03_Image/pages/rom_04454c.png) | 256×144 | `rom_04454c` | GAME OVER 画面 |
| [rom_044734.png](../03_Image/pages/rom_044734.png) | 256×144 | `rom_044734` | CONTINUE 画面 |
| [rom_05c000.png](../03_Image/pages/rom_05c000.png) | 256×144 | `rom_05c000` | 配置页整包（256 图块 + 地图） |
| [rom_060000.png](../03_Image/pages/rom_060000.png) | 256×144 | `rom_060000` | 标题画面·第二版整包（历史副本） |
| [rom_064000.png](../03_Image/pages/rom_064000.png) | 256×144 | `rom_064000` | 场景 1 介绍·早期整包（历史副本） |
| [rom_0646fa.png](../03_Image/pages/rom_0646fa.png) | 256×144 | `rom_0646fa` | 场景 2 介绍·早期整包（历史副本） |
| [rom_06c000.png](../03_Image/pages/rom_06c000.png) | 256×144 | `rom_06c000` | 场景 1 介绍整包（128 图块 + 地图） |
| [rom_06c70b.png](../03_Image/pages/rom_06c70b.png) | 256×144 | `rom_06c70b` | 场景 2 介绍整包 |
| [rom_06cda8.png](../03_Image/pages/rom_06cda8.png) | 256×144 | `rom_06cda8` | 场景 3 介绍整包 |
| [rom_06d490.png](../03_Image/pages/rom_06d490.png) | 256×144 | `rom_06d490` | 场景 4 介绍整包 |
| [rom_06db85.png](../03_Image/pages/rom_06db85.png) | 256×240 | `rom_06db85` | 场景 5 介绍整包（240 px 高） |
| [rom_070000.png](../03_Image/pages/rom_070000.png) | 256×144 | `rom_070000` | 标题画面整包（中文 Logo + 额外游戏 + 菜单） |

