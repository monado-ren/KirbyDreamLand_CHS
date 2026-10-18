# 版本记录

## v0.5.1 源码工程改进 — 符号层成为唯一补丁来源、RGBDS 从源码编译（ROM 与补丁不变）

- `source/manifest.json` 不再存 110 处 `expected_hex/replacement_hex`：加载清单时由
  `source/change_surface.json` 派生补丁，代码区域用 RGBDS 汇编
  `source/patches/vblank_two_row.rev1.asm` 与 `vblank_two_row.asm`，清单只保留一个
  `change_surface.sha256` 摘要。`sync-manifest --write` 可重写清单，结果逐字节一致。
- 新增 `tools/build_rgbds.py`：从 pinned 的 RGBDS v1.0.4 源码 tarball（SHA-256 固定）下载、
  `make` 编译并安装到 gitignored 的 `build/rgbds`；构建/测试现在始终使用源码编译的汇编器。
- 编辑页的 10 个基线外部图块由 160 B hex 改为 baserom provenance（stream 偏移 + tile 序号）。
- 校验字段精简：去掉 manifest 的 MD5/SHA-1 与每资源 `packed_sha256`，只保留输入/输出 SHA-256、
  每资源 `decoded_sha256` 与尺寸；`check_base` 只输出 SHA-256。
- 编辑用字形子集不再入库：`assets/fonts/*.json` 由 `tools/fetch_fonts.py` 从上游 pinned
  ZLabs Pixel 12px `.kbitx` 与 Fusion Pixel 8px BDF 发行包（SHA-256 固定）生成，glyphs 与
  既有文件逐项一致；上游字体许可与声明保留。开发侧新增 `requirements-dev.txt`（kbitfont）。
- 新增 `tools/audit_pages.py`：静态审计 48 个页面的 VRAM/tile/地图预算、外部基线图块引用、
  装载目的与容量余量，生成 `docs/PAGE_BUDGET.md`；`--check` 纳入验证，但不替代实机验证。
- CI 增加 `pip install -r requirements.txt` 与 `python tools/build_rgbds.py`；
  ROM、xdelta3 补丁与目标哈希（`f96fe0ec…2795`）不变。公开测试 130 项。


## v0.5.1 源码工程改进 — PNG 编解码改用 Pillow（ROM 与补丁不变）

- `tools/graphics_png.py` 的 PNG 编解码由自写 stdlib 实现改为 **Pillow**（`requirements.txt`
  钉住 `Pillow==13.0.0`（Python ≥3.11））；保留全部严格校验：拒绝透明/alpha、隔行、非规范四色、
  尺寸/图块数不符、损坏 chunk 校验和。
- 所有受影响的生成 PNG（71 份 `source/graphics` 源、21 张 bundle 页、27 份覆盖层图集）
  用 Pillow 重新编码；解码出的游戏字节不变，因此 **ROM、xdelta3 补丁和目标哈希
  （`f96fe0ec…2795`）不变**。
- 新增 `requirements.txt`；CI 增加 `pip install -r requirements.txt`；
  `THIRD_PARTY_NOTICES.md` 与 `LICENSES/Pillow-HPND.txt` 记录 Pillow 的 HPND 许可。
- 公开测试仍为 125 项。


## v0.5.1 源码工程改进 — 页面层改为基线+覆盖层（ROM 与补丁不变）

- 27 个页面（23 张图鉴/通关提示 + 4 张图块画布）不再存整页 PNG，改为
  `source/edits/<id>.json` + `<id>_cells.png`：基线由用户自备的 Rev1 ROM 重建（原始图块/地图
  + 少量 pinned 外部图块），仓库只保存改动的 8×8 格子。21 张 bundle 页（关卡介绍、标题、配置、
  声音测试、GAME OVER、CONTINUE）保持整页 PNG。
- 新增 `tools/page_edits.py`（render/check/extract）：在 gitignored 的 `build/pages/` 重建整页、
  校验基线+覆盖层 == 由 `source/graphics` 渲染的页面，并把编辑后的页面折回覆盖层。
- `tools/pages.py` 同时处理两种页面；编辑 `build/pages/<id>.png` 后 retile 会回写图块集/地图并
  刷新覆盖层。`source/pages` + `source/edits` 合计约 51 KB（原 72 KB），页面语义不变。
- ROM、xdelta3 补丁与目标哈希（`f96fe0ec…2795`）完全不变；公开测试仍为 125 项。


## v0.5.1 源码工程改进 — 改动面符号化（ROM 与补丁不变）

- 新增 `source/change_surface.json`：把 110 处原银行补丁（198 字节）和 71 个扩展资源从原始 hex
  提升为语义层——装载点名称、目标资源、旧值→新值、用途说明、25 个历史副本的保留原因、校验和策略。
- 新增 `tools/change_surface.py`：`check` 证明符号层精确派生出 `source/manifest.json`（含 baserom
  前置字节与哈希核对），`explain`/`resources`/`dump` 提供人话审阅。
- manifest 的 `patches` 段现在由符号层生成：`sync-manifest --write` 重写清单，结果与 v0.5.1
  现有清单逐字节一致（不再手写 hex）；`sync-manifest` 无参数时只校验。
- 唯一的游戏逻辑补丁（两行 vblank 写入器）升级为指令级：`source/patches/vblank_two_row.asm`
  用 RGBDS 汇编，41 字节区域与 Rev1 的差异自动派生为 manifest 的 4 段补丁；外部 RGBDS 只用于
  开发期校验/修改（`assemble --write`、`check --rgbds`），stdlib 构建仍只用固定字节。
- `tools/build.py`、`tools/verify.py`、`tools/selftest.py` 在使用默认清单时强制核对符号层；
  新增 `tests/test_change_surface.py`，公开测试增至 125 项。
- ROM、xdelta3 补丁与目标哈希（`f96fe0ec…2795`）完全不变。


## v0.5.1 源码工程改进 — 图形资源改为无损 PNG（ROM 与补丁不变）

- 71 份解码后的 2bpp 图形资源由 `source/resources/*.bin` 改为 `source/graphics/*.png`：48 份 4 色索引图块集、23 份 32×32 8 位灰度图块表。
- 新增仅用标准库的 PNG 编解码器 `tools/graphics_png.py`；构建从 PNG 派生原始字节，继续校验派生/压缩哈希、容量、银行边界与 HAL 往返。
- 严格拒绝透明、抗锯齿／非调色板颜色、隔行 PNG、尺寸或图块数不符的编辑，避免静默近似。
- 新增 `tools/derive_resources.py`，可把派生字节导出到 gitignored 的 `build/resources/` 供比对。
- 新增可读页面层 `source/pages/*.png`（23 张 32×32 整页合成图）与 `tools/pages.py`：`render/--check` 维护预览，`retile` 把编辑后的页面可逆拆回图块集+索引表；未编辑页面保证逐字节还原。
- 编辑后超出原分配容量时，`retile` 可把资源重分配到扩展 ROM 空闲银行并自动改写加载指针补丁（`tools/allocation.py`），同时输出重分配报告。
- 识别出 21 个「tiles + map」bundle 资源（场景介绍 128 图块+32×18 地图、场景 5 128+32×30、配置页 256+32×18、标题页 292+32×18 等），拆成图块 PNG + `<id>_map.png` 地图 PNG，并可合成为可读页面。
- 页面总数 48：23 张背景页、21 张 bundle 页、4 张图块画布（HUD、结局精灵、开场装饰）；bundle 页面中引用原始 ROM 图块的格子显示为占位图案且只读。
- 图块槽位按游戏加载器固定，retile 新增图案时通过压缩去重（保留/首用/排序三种策略）确保不超出原有槽位数。
- 用 PNG 源重建的输出 ROM 与 v0.5.1 发布目标逐字节一致（SHA-256 `f96fe0ec…2795`），已跟踪的 xdelta3 补丁无需改动。

## v0.5.1 — 首次整理为独立 Rev 1 补丁工程

- 固定日版 Rev 1 输入的 MD5、SHA-1、SHA-256，保留其原有程序修复。
- 独立源码构建结果精确复现 `kirby_jp_rev1_zh_v0.5.1_stage5_up2.gb`。
- 场景 5 的“场景5”“帝帝帝山”一起上移 2 像素；位置水平居中、字形不变。
- 整理 71 份扩展资源、原银行局部补丁、核稿文本、编辑素材及许可。
- 原版及构建 ROM 不提交；提交 `KirbyDreamLand_CHS-Monado.xdelta3`。
- 后续修订以本仓库的源码、清单和补丁为版本管理入口。

此前工作目录的历史版本未作为完整 ROM 导入 Git。
