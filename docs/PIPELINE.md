# 工序目录（参考 PKMN_GSCHS 的组织）

本仓库采用编号工序目录，同时保留旧路径的符号链接，避免破坏既有命令与清单引用：

```text
00_Tools/        构建、验证、页面、审计、字体/RGBDS 工具
01_Export/       导出/溯源入口（实际数据在 04_Data、03_Image/edits、06_ProgramFix）
02_Text/         审稿文本（非自动渲染输入）
03_Image/        图形：graphics（构建权威）、pages（bundle 页）、edits（基线+覆盖层）、artwork
04_Data/         manifest.json、assets.json
05_Font/         pinned 上游字体与生成说明（生成物 gitignored）
06_ProgramFix/   change_surface.json、patches/*.asm（补丁唯一来源）
patches/         发布 xdelta3 补丁
```

与 PKMN_GSCHS 的对应关系：

| PKMN_GSCHS | 本仓库 |
| --- | --- |
| 00_Tools | `00_Tools/`（纯 Python + 可选 RGBDS；无 Windows exe） |
| 01_Export | `01_Export/` 文档入口；实际 provenance 在 `03_Image/edits`、`06_ProgramFix/change_surface.json` |
| 02_Text | `02_Text/`（当前仅审稿，非渲染输入） |
| 03_Image | `03_Image/`（PNG + 页面/覆盖层 + provenance） |
| 04_Data | `04_Data/`（JSON 清单，替代 xlsx） |
| 05_Font | `05_Font/`（pinned 上游生成，字体二进制不入库） |
| 02_Text | `02_Text/`（审稿 + `layout.json` 文本层；11 条文本已可重排） |
| 06_ProgramFix | `06_ProgramFix/change_surface.json + patches/*.asm`（符号 + 汇编） |
| patches/ | `patches/`（xdelta3，非 IPS） |

刻意不照搬：Windows 工具、ROM 手工导入、xlsx/Numbers 数据源、二进制字体入仓、IPS-only 流程。
构建与验证以 `04_Data/manifest.json` 和 `03_Image/graphics` 为准。
