# 03_Image — 图形与页面

| 子目录 | 内容 | 角色 |
| --- | --- | --- |
| `graphics/` | 92 张无损 PNG：图块集、背景索引表、bundle 地图 | **构建权威** |
| `pages/` | 21 张 bundle 整页 PNG（关卡介绍、标题、配置、声音测试、GAME OVER、CONTINUE） | 可读/可编辑页 |
| `edits/` | 27 个“基线+覆盖层”页：JSON + `*_cells.png` | 只存改动格子，基线来自用户自备 Rev1 |
| `artwork/` | 选定的修订素材/Logo 参考 | 编辑参考，不直接进构建 |

构建读取 `03_Image/graphics`；页面层用 `00_Tools/pages.py retile` 回写 graphics。
