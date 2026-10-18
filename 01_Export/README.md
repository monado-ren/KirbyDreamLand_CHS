# 01_Export — 导出与溯源

本仓库没有独立的文本导出二进制；导出/定位结果以可 diff 的 JSON 与报告形式存放：

- 资源与 loader 溯源：`../06_ProgramFix/change_surface.json`（47 sites、71 resources、110 patches）
- 资源布局与哈希：`../04_Data/manifest.json`
- 页面基线来源（Rev1 bank/CPU、changed cells、外部图块 provenance）：`../03_Image/edits/*.json`
- 预算/运行时核对报告：`../docs/PAGE_BUDGET.md`、`../docs/VISUAL_REGRESSION_AUDIT.md`

导出的图形不是本目录的副本：构建权威是 `../03_Image/graphics/*.png`，整页视图是
`../03_Image/pages/` 与 `../03_Image/edits/`。
