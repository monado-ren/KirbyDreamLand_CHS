# 版本记录

> 本仓库与原开发工作区并行编号，`v0.5.2` 在两处含义不同；
> 见 [版本谱系与并行编号](docs/VERSION_LINEAGE.md)。

## v0.5.2 删除死装载 — 实际装载快 10.3 帧

- 标题页与配置页的整包会**完全覆盖**同段代码里前面几次装载的 VRAM 区间：
  标题页 `$8800+5248` 覆盖 `$8800-$9C80`，把 tiles1/tiles2/font 三次装载全部盖掉；
  配置页 `$8800+4672` 覆盖 `$8800-$9A40`，把 hud/tiles/font 三次装载全部盖掉。
  这 6 次 `CALL $20C1` 是移植时留下的死装载，**结果永远看不到**。
- v0.5.2 把这 6 个 `CALL` 改成 NOP（新增补丁类型 `code.nop`，18 字节），
  载荷 81,056 → **75,024** 字节，相对原版从 +21% 降到 **+12%**，约省 **10.3 帧**。
- 验证方式：`audit_dead_loads.py` 用 VRAM 区间覆盖证明每一次都真死；模拟器逐帧比对
  确认“对齐到同一游戏事件”后标题页/配置页的 VRAM、BG map、OAM、I/O 全部一致。
- 可逆：把这 6 处改回 `CD C1 20` 并重算校验和，逐字节恢复 v0.5.1 的 ROM 哈希。
- 说明：这 10.3 帧**不足以**让外部 TAS 直接可用——剩余 +8,304 字节是中文图块复杂度的
  固有成本，TAS 仍会因每次进这些页面而累积偏移。

## v0.5.1 装载载荷审计 — 可压缩空间

- 新增 `00_Tools/audit_loader_payload.py` + `docs/LOADER_PAYLOAD.md`：量化 5 张变大的整包页里
  有多少 tile 是地图从未引用的。结果：17,792 decoded 字节中只剩 5,776 是必需的（**-68%**），
  重排后页面 PNG 逐像素不变（工具实际渲染比对）。
- 但地图字节就是 VRAM tile 编号、OAM 精灵也指向同一块 VRAM，重排属于“改 tile ID 契约”，
  不是纯数据优化；是否值得做见文档结论。


## v0.5.1 装载成本 — 静态审计

- 新增 `00_Tools/audit_loader_timing.py`：从 `baserom.gb` 解出每个 loader 原版载荷大小，
  与汉化资源对比，量化“装载变慢”的来源：41 个 loader 总载荷 66,720 → 81,056 字节
  （**+21%**），标题/配置各 +4096，声音测试/失败/继续各 +2048，其余不变。
- 生成 `docs/LOADER_TIMING.md`；并在 `docs/PLAYTHROUGH.md` 说明为什么外部 TAS/逐帧截图
  不能按固定帧偏移对齐（装载循环每帧吞吐固定，但总数据量变大，且每次装载都会多花帧）。


## v0.5.1 文本层扩展 — 76 条 / 26 页

- 文本层从 11 条 / 8 页扩到 **76 条 / 26 页**：新增图鉴 14 页 48 条角色名、
  2 张通关提示 8 条（含 7 处用户核定标点的逐格覆盖）、HUD 2 页的“卡比/积分”、
  5 个“场景”序号。
- 新增权威排版数据 `02_Text/gallery-layout.json`、`hint-layout.json`、`hud-layout.json`
  （来自已批准的开发工作区布局，坐标不是 ROM 数据）。
- `text_layout.py` 支持两种模式：`page`（bundle 页提交去字底图）与 `edit`
  （图鉴/提示/HUD 不提交底图，按 Rev1 重建后验证/回写）。
- 验证：`TEXT_RENDER=PASS ENTRIES=76 PAGES=26 BASE_PAGES=8`；ROM、补丁、页面哈希不变。


## v0.5.1 文档 — 工序与修改内容清单

- `00_Tools/change_surface.py` 新增 `report` / `report --check`：从符号层和清单生成
  `docs/WORK_ITEMS.md`（9 道工序 + 110 处补丁逐条 + 71 个资源 + 11 条文本层 + 48 页 + 121 条译文；
  另含从素材到发布的 10 步操作工序），CI 校验文档与符号层同步。
- `change_surface.py summary` 输出分层构成单行摘要。


## v0.5.1 文本层 — 字体 + 译文 + 布局生成页面

- 新增 `00_Tools/text_layout.py` 与 `02_Text/layout.json`、`03_Image/text-base/*.png`：
  8 个页面 / 11 条文本（场景 1–5 关卡名、声音测试、GAME OVER、CONTINUE）不再只存结果像素，
  而是“底图 + 字体 + 译文 + 锚点”可重排；`text_layout.py check` 验证
  `base + font(translation, layout)` 与已提交页面逐像素一致。
- `05_Font/generated` 的 8px 子集扩展到 56 个字形（覆盖通关提示文本），字形摘要仍为 pinned。
- 其余页面（配置、标题、图鉴、通关提示等）文字仍为人工排版像素，继续按页面/覆盖层维护；
  ROM、补丁与目标哈希不变。


## v0.5.1 工程组织 — 按工序编号目录（参考 PKMN_GSCHS）

- 目录改为 `00_Tools/`、`01_Export/`、`02_Text/`、`03_Image/`、`04_Data/`、`05_Font/`、
  `06_ProgramFix/`、`patches/`；不再使用 `source/*`、`tools/`、`translations/` 旧路径。
- 内容映射：`00_Tools`（工具）、`02_Text`（审稿）、`03_Image`（graphics/pages/edits/artwork）、
  `04_Data`（manifest/assets）、`05_Font`（pinned 上游字体生成物 gitignored）、
  `06_ProgramFix`（change_surface + asm）、`patches`（发布 xdelta3）。
- 只借鉴分阶段组织，不引入 PKMN_GSCHS 的 Windows 二进制工具、ROM 手工导入、xlsx 数据源；
  构建仍是纯 Python + Pillow + 源码编译 RGBDS，ROM/补丁哈希不变。

## v0.5.1 源码工程改进 — 符号层成为唯一补丁来源、RGBDS 从源码编译（ROM 与补丁不变）

- `04_Data/manifest.json` 不再存 110 处 `expected_hex/replacement_hex`：加载清单时由
  `06_ProgramFix/change_surface.json` 派生补丁，代码区域用 RGBDS 汇编
  `06_ProgramFix/patches/vblank_two_row.rev1.asm` 与 `vblank_two_row.asm`，清单只保留一个
  `change_surface.sha256` 摘要。`sync-manifest --write` 可重写清单，结果逐字节一致。
- 新增 `00_Tools/build_rgbds.py`：从 pinned 的 RGBDS v1.0.4 源码 tarball（SHA-256 固定）下载、
  `make` 编译并安装到 gitignored 的 `build/rgbds`；构建/测试现在始终使用源码编译的汇编器。
- 编辑页的 10 个基线外部图块由 160 B hex 改为 baserom provenance（stream 偏移 + tile 序号）。
- 校验字段精简：去掉 manifest 的 MD5/SHA-1 与每资源 `packed_sha256`，只保留输入/输出 SHA-256、
  每资源 `decoded_sha256` 与尺寸；`check_base` 只输出 SHA-256。
- 编辑用字形子集不再入库：`05_Font/generated/*.json` 由 `00_Tools/fetch_fonts.py` 从上游 pinned
  ZLabs Pixel 12px `.kbitx` 与 Fusion Pixel 8px BDF 发行包（SHA-256 固定）生成，glyphs 与
  既有文件逐项一致；上游字体许可与声明保留。开发侧新增 `requirements-dev.txt`（kbitfont）。
- 新增 `00_Tools/audit_pages.py`：静态审计 48 个页面的 VRAM/tile/地图预算、外部基线图块引用、
  装载目的与容量余量，生成 `docs/PAGE_BUDGET.md`；`--check` 纳入验证，但不替代实机验证。
- 新增 `00_Tools/audit_visual_regression.py`：核对 BGB 1.6.6 视觉回归包（32 屏、原生 state、
  VRAM/BG map/OAM/IO）与页面源；30/30 活跃页面覆盖，29 PASS + 2 PASS_DYNAMIC，0 FAIL；
  生成 `docs/VISUAL_REGRESSION_AUDIT.md`。
- 修正两张通关提示页的语义：`rom_055050` 是普通模式通关后提示如何进入额外模式，
  `rom_056110` 是额外模式通关后提示如何进入配置模式；`change_surface.json` 的 purpose
  及页面/预算/视觉回归报告同步更新（补丁与 ROM 不受影响）。
- CI 增加 `pip install -r requirements.txt` 与 `python 00_Tools/build_rgbds.py`；
  ROM、xdelta3 补丁与目标哈希（`f96fe0ec…2795`）不变。公开测试 130 项。


## v0.5.1 源码工程改进 — PNG 编解码改用 Pillow（ROM 与补丁不变）

- `00_Tools/graphics_png.py` 的 PNG 编解码由自写 stdlib 实现改为 **Pillow**（`requirements.txt`
  钉住 `Pillow==13.0.0`（Python ≥3.11））；保留全部严格校验：拒绝透明/alpha、隔行、非规范四色、
  尺寸/图块数不符、损坏 chunk 校验和。
- 所有受影响的生成 PNG（71 份 `03_Image/graphics` 源、21 张 bundle 页、27 份覆盖层图集）
  用 Pillow 重新编码；解码出的游戏字节不变，因此 **ROM、xdelta3 补丁和目标哈希
  （`f96fe0ec…2795`）不变**。
- 新增 `requirements.txt`；CI 增加 `pip install -r requirements.txt`；
  `THIRD_PARTY_NOTICES.md` 与 `LICENSES/Pillow-HPND.txt` 记录 Pillow 的 HPND 许可。
- 公开测试仍为 125 项。


## v0.5.1 源码工程改进 — 页面层改为基线+覆盖层（ROM 与补丁不变）

- 27 个页面（23 张图鉴/通关提示 + 4 张图块画布）不再存整页 PNG，改为
  `03_Image/edits/<id>.json` + `<id>_cells.png`：基线由用户自备的 Rev1 ROM 重建（原始图块/地图
  + 少量 pinned 外部图块），仓库只保存改动的 8×8 格子。21 张 bundle 页（关卡介绍、标题、配置、
  声音测试、GAME OVER、CONTINUE）保持整页 PNG。
- 新增 `00_Tools/page_edits.py`（render/check/extract）：在 gitignored 的 `build/pages/` 重建整页、
  校验基线+覆盖层 == 由 `03_Image/graphics` 渲染的页面，并把编辑后的页面折回覆盖层。
- `00_Tools/pages.py` 同时处理两种页面；编辑 `build/pages/<id>.png` 后 retile 会回写图块集/地图并
  刷新覆盖层。`03_Image/pages` + `03_Image/edits` 合计约 51 KB（原 72 KB），页面语义不变。
- ROM、xdelta3 补丁与目标哈希（`f96fe0ec…2795`）完全不变；公开测试仍为 125 项。


## v0.5.1 源码工程改进 — 改动面符号化（ROM 与补丁不变）

- 新增 `06_ProgramFix/change_surface.json`：把 110 处原银行补丁（198 字节）和 71 个扩展资源从原始 hex
  提升为语义层——装载点名称、目标资源、旧值→新值、用途说明、25 个历史副本的保留原因、校验和策略。
- 新增 `00_Tools/change_surface.py`：`check` 证明符号层精确派生出 `04_Data/manifest.json`（含 baserom
  前置字节与哈希核对），`explain`/`resources`/`dump` 提供人话审阅。
- manifest 的 `patches` 段现在由符号层生成：`sync-manifest --write` 重写清单，结果与 v0.5.1
  现有清单逐字节一致（不再手写 hex）；`sync-manifest` 无参数时只校验。
- 唯一的游戏逻辑补丁（两行 vblank 写入器）升级为指令级：`06_ProgramFix/patches/vblank_two_row.asm`
  用 RGBDS 汇编，41 字节区域与 Rev1 的差异自动派生为 manifest 的 4 段补丁；外部 RGBDS 只用于
  开发期校验/修改（`assemble --write`、`check --rgbds`），stdlib 构建仍只用固定字节。
- `00_Tools/build.py`、`00_Tools/verify.py`、`00_Tools/selftest.py` 在使用默认清单时强制核对符号层；
  新增 `tests/test_change_surface.py`，公开测试增至 125 项。
- ROM、xdelta3 补丁与目标哈希（`f96fe0ec…2795`）完全不变。


## v0.5.1 源码工程改进 — 图形资源改为无损 PNG（ROM 与补丁不变）

- 71 份解码后的 2bpp 图形资源由早期 `source/resources/*.bin` 改为 `03_Image/graphics/*.png`：48 份 4 色索引图块集、23 份 32×32 8 位灰度图块表。
- 新增仅用标准库的 PNG 编解码器 `00_Tools/graphics_png.py`；构建从 PNG 派生原始字节，继续校验派生/压缩哈希、容量、银行边界与 HAL 往返。
- 严格拒绝透明、抗锯齿／非调色板颜色、隔行 PNG、尺寸或图块数不符的编辑，避免静默近似。
- 新增 `00_Tools/derive_resources.py`，可把派生字节导出到 gitignored 的 `build/resources/` 供比对。
- 新增可读页面层 `03_Image/pages/*.png`（23 张 32×32 整页合成图）与 `00_Tools/pages.py`：`render/--check` 维护预览，`retile` 把编辑后的页面可逆拆回图块集+索引表；未编辑页面保证逐字节还原。
- 编辑后超出原分配容量时，`retile` 可把资源重分配到扩展 ROM 空闲银行并自动改写加载指针补丁（`00_Tools/allocation.py`），同时输出重分配报告。
- 识别出 21 个「tiles + map」bundle 资源（场景介绍 128 图块+32×18 地图、场景 5 128+32×30、配置页 256+32×18、标题页 292+32×18 等），拆成图块 PNG + `<id>_map.png` 地图 PNG，并可合成为可读页面。
- 页面总数 48：23 张背景页、21 张 bundle 页、4 张图块画布（HUD、结局精灵、开场装饰）；bundle 页面中引用原始 ROM 图块的格子显示为占位图案且只读。
- 图块槽位按游戏加载器固定，retile 新增图案时通过压缩去重（保留/首用/排序三种策略）确保不超出原有槽位数。
- 用 PNG 源重建的输出 ROM 与 v0.5.1 发布目标逐字节一致（SHA-256 `f96fe0ec…2795`），已跟踪的 xdelta3 补丁无需改动。

## v0.5.1 — 首次整理为独立 Rev 1 补丁工程

- 固定日版 Rev 1 输入的 MD5、SHA-1、SHA-256，保留其原有程序修复。
- 独立源码构建结果精确复现 `kirby_jp_rev1_zh_v0.5.1_stage5_up2.gb`。
- 场景 5 的“场景5”“帝帝帝山”一起上移 2 像素；位置水平居中、字形不变。
- 整理 71 份扩展资源、原银行局部补丁、核稿文本、编辑素材及许可。
- 原版及构建 ROM 不提交；提交 `patches/KirbyDreamLand_CHS-Monado.xdelta3`。
- 后续修订以本仓库的源码、清单和补丁为版本管理入口。

此前工作目录的历史版本未作为完整 ROM 导入 Git。
