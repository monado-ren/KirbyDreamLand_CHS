# 04_Data — 清单与数据

- `manifest.json`：71 个资源（46 active + 25 legacy）的 bank/offset/capacity、PNG 源、decoded size/SHA-256、page/edit 引用；不存补丁 hex。
- `assets.json`：编辑素材/字体/许可的来源与哈希记录。

`00_Tools`/`tests` 通过本目录的 `manifest.json` 与 `assets.json` 读取数据。
补丁的语义源在 `../06_ProgramFix/change_surface.json`，清单只保留一个派生摘要。
