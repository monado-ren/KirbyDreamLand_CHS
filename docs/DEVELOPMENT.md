# 构建与后续修订

## 唯一输入与构建方式

只接受仓库根目录的 `baserom.gb`（日本 Rev 1、256 KiB）。源码构建的全部输入为它及 `source/`；
不依赖旧 ROM、成品 ROM 或旧开发工程。Python 侧依赖 Pillow（PNG 编解码，版本钉在 `requirements.txt`）；
代码补丁的指令级来源是 `source/patches/*.asm`，由 RGBDS（`python tools/build_rgbds.py` 从 pinned
源码编译）在加载清单时汇编，因此常规构建也需要 RGBDS。

`source/manifest.json` 声明版本、三个输入/输出哈希、原银行修改的前置字节、扩展资源地址、银行号、容量、原始和压缩摘要。构建步骤：

1. 核验输入大小及 SHA-256。
2. 以原版字节为底，扩容至 512 KiB，空白区填 `FF`。
3. 校验 110 段局部补丁前置字节后写入，共 198 个原银行字节；校验和另算。
4. 将 71 份 `source/graphics/*.png` 无损派生成 2bpp 图块/图块表字节（共 150560 字节），重新 HAL 压缩并按清单写入。逐条验证 PNG 模式与尺寸、规范配色、派生大小、摘要、解压往返、银行边界及不重叠。
5. 重算 Game Boy 头部和全局校验和，检查最终三个哈希及保留的 Rev 1 修复。

71 份资源包括 25 份当前载入器未引用的旧资源，清单已标注。这些字节仍存在于既定 v0.5.1 中，为保证与指定成品 **Hash 一致**而保留，不应擅自清零。

## 符号化改动面

`source/change_surface.json` 是改动面的唯一来源：清单不再存 110 处补丁 hex，只存一个派生摘要；每个装载点有名称、目标资源、旧值→新值和用途，
每个资源标记 active/legacy 及历史原因，代码补丁带指令级注释。它不直接参与构建，但必须精确派生出
`source/manifest.json` 的 110 处补丁（198 字节）；默认清单的 `tools/build.py`、`tools/verify.py`、
`tools/selftest.py` 都会核对，`python tools/change_surface.py check --base baserom.gb` 可单独检查，
`explain` 可生成人话审阅列表。唯一的代码补丁是 RGBDS 汇编的 `source/patches/vblank_two_row.asm`
（`code.region`，41 字节区域 → manifest 4 段差异）；安装外部 RGBDS 后可 `assemble --write` 同步、
`check --rgbds ...` 重新汇编校验，但常规构建只依赖已固定的 `new_hex`。字段与修改流程见
[符号化改动面](CHANGE_SURFACE.md)。

## 文件不是完整反汇编工程

`source/graphics/` 是实际参与构建的图形源，而不是整份 ROM 的改名或封装：48 份为 4 色索引 PNG 的 2bpp 图块集，23 份为 32×32、8 位灰度的图块索引表，均可无损派生为游戏使用的原始字节。原版代码和未改动数据来自用户的输入。

`translations/` 和 `assets/` 提供核稿文本及编辑参考；编辑用字形子集不随仓库分发，
运行 `python -m pip install -r requirements-dev.txt && python tools/fetch_fonts.py`
从上游 pinned 字体源生成（gitignored）。当前工具不自动将全部译文、assets/ 图稿或字体重排为游戏页面；修改它们后必须同步修改对应 `source/graphics/*.png`、指针或新增编译接口，再进行验证。

## 修改一份既有图形资源

先用清单的 `label`、`offset`、`bank`、`cpu_address`、当前引用状态定位正确版本。例如场景 5 当前包位于 ROM `0x6DB85`，源为 `source/graphics/r_06db85.png`。

### PNG 源规范

| 类型 | 清单 `png.mode` | 规则 |
| --- | --- | --- |
| 图块集 | `tiles-2bpp-4gray` | 4 色索引 PNG，宽 = `tiles_per_row × 8`；每 8×8 像素为一块 2bpp 图块，按行优先顺序排列；最后一行的白色补齐格在构建时忽略 |
| 图块表 | `tilemap-8bpp-grayscale` | 32×32、8 位灰度 PNG，一个像素就是一个图块索引字节（0–255） |

两种模式都只接受四种灰度：`255`（2bpp 值 0）、`170`（1）、`85`（2）、`0`（3）。索引 PNG 的调色板颜色可以重新排列，但像素颜色必须精确等于这四色之一。**透明通道、抗锯齿／插值产生的中间色、隔行 PNG、错误的宽高或图块数变化都会被构建立即拒绝**，不会静默取整。`tools/derive_resources.py` 可把派生的 `.bin` 写到 gitignored 的 `build/resources/`，便于与旧快照逐字节比对。

以下流程适用于保持图块数与分配地址不变、容量足够的修改：

```sh
git switch -c codex/my-localization-change
# 编辑对应 source/graphics/*.png；同时更新译文/美术参考与测试。
python tools/repack.py --version v0.5.2-dev.1
python tools/build.py --manifest build/manifest.edited.json --output build/check.gb
python tools/verify.py --manifest build/manifest.edited.json --rom build/check.gb --base baserom.gb
python tools/release.py --manifest build/manifest.edited.json --output build/check.gb --patch build/check.xdelta3
```

`repack.py` 默认生成独立开发清单 `build/manifest.edited.json`，保留已发布清单；常规构建会拒绝未登记的资源变化。压缩结果超出分配容量、改变派生长度或需要移动指针的修改，应先扩展清单与对应构建/测试，不能靠截断数据处理。

审核通过后，将开发清单的完整内容作为新的 `source/manifest.json`，使用新版本号，更新 `CHANGELOG.md` 和目标哈希，再运行 `python tools/release.py`。新源码资源、清单与命名 xdelta3 补丁在同一提交中更新。原版的三个输入哈希保持不变。

### 整页编辑（source/pages + source/edits）

`source/` 下共 48 个页面，按存储方式分两类：

| 存储 | 数量 | 页面结构 | 说明 |
| --- | --- | --- | --- |
| `source/pages/<id>.png` | 21 | `bundle`：单资源 = 图块块 + 地图块（场景介绍 128+32×18、场景 5 128+32×30、配置 256+32×18、标题 292+32×18 等） | 整页 PNG 直接可读可编辑 |
| `source/edits/<id>.json` + `<id>_cells.png` | 27 | `tilemap`（23：图鉴/通关提示，独立图块集 + 32×32 索引表）与 `sheet`（4：HUD、结局精灵、开场装饰） | **基线+覆盖层**：基线由用户自备的 Rev1 ROM 重建（原始图块/地图，加少量 pinned 外部图块），仓库只保存改动的 8×8 格子 |

基线+覆盖层页的编辑流程：

1. `python tools/page_edits.py render` 把 27 个页面重建到 gitignored 的 `build/pages/`；
2. 编辑 `build/pages/<id>.png`；
3. `python tools/pages.py retile build/pages/<id>.png`：把编辑后的页面拆回 `source/graphics/` 图块集/索引表，并刷新 `source/edits/` 的覆盖层图集与格子索引；
4. `python tools/pages.py render --check` 与 `python tools/page_edits.py check` 校验两种页面都与 `source/graphics` 一致（后两者需要 `baserom.gb`）。

bundle 页面仍在 `source/pages/<id>.png` 直接编辑并 `python tools/pages.py retile source/pages/<id>.png`。bundle 页面里引用原始 ROM 图块（无法归属本资源）的格子显示为占位图案、retile 时只读；图块槽位数由游戏加载器固定，新增图案通过压缩去重腾出槽位，不会擅自增加加载长度。

若资源超出原分配容量，retile 会先用更紧凑的编码，并把仍放不下的资源重分配到扩展 ROM 的空闲空间（如 bank 24–29 的空隙），同时自动改写清单中对应的加载指针补丁。输出中的 `RELOCATE=…` 报告新 bank/CPU 地址与改写补丁数；这会改变 ROM 布局与哈希，属于自定义修订，发布前必须重新生成补丁。之后按本节前面的流程运行 `tools/repack.py` 生成开发清单，再构建、验证、发布。

限制：使用 `0x8800` 寻址的两页通关提示只能复用可寻址图块或整体压缩重排；指针改写只覆盖清单中已登记的加载点，模拟器/真实硬件验证仍不可省略。

页面预算审计：`python tools/audit_pages.py --write` 生成 `docs/PAGE_BUDGET.md`（48 页的 tile 数、地图码、外部基线引用、装载目的、容量余量）；`--check` 在容量等硬约束不成立时失败。静态审计不替代实机验证。

运行时抽检：`docs/PLAYTHROUGH.md` 描述用 PyBoy 完整游玩一次、自动记录 VRAM/BG map 并匹配页面的流程（`tools/play_capture.py` 录制输入+VRAM，`tools/replay_inputs.py` 确定性重放，`tools/analyze_playthrough.py` 匹配页面）；另有外部 BGB 视觉回归包核对工具 `tools/audit_visual_regression.py`（生成 `docs/VISUAL_REGRESSION_AUDIT.md`）。这些都是本地可选验证，不进入公开 CI。

## 地址与 Rev 1 约束

| 项目 | ROM 偏移与字节 |
| --- | --- |
| 星星存在检测 | `0x37B1: FA 14 D4 A7 C0` |
| 起跳清除 D414 | `0x434B: EA 14 D4` |
| 风语大树图形槽耗尽兜底 | `0x1418C: 38 07` |
| 振翅蝙蝠图鉴专用 X 调整 | `0x3DA1F: EF`，只改这一专用横坐标 |
| 对应 Rev 1 动画指针 | 保留银行 `08:5319`，不是旧版 `08:5311` |
| 场景 5 资源指针 | `0x190C7: 1B 5B 85` |
| 场景 5 压缩包 | ROM `0x6DB85`，银行 `1B:5B85`，1668 字节 |

原银行代码不是直接用旧日版替换；先验字节检查及关键修复检查必须保持。新增银行切换、RAM 使用或指针调整需单独审查，不能把旧版偏移当作 Rev 1 偏移。

## 像素和动态验证

- 可见屏幕 160×144，底层地图可能更大；检查滚动及屏外像素。
- 原尺寸、四级灰度，不使用平滑缩放、抗锯齿或仿色。
- 数字保留原字形；文字与动态精灵分别处理。
- 场景 5 两行文字已上移 2 像素，最大文字 Y 为 47；滚动 SCY=48 时不应在屏顶残留文字。
- 图鉴背景不烘焙角色和动态五官。实际运行还需检查动画、遮挡、VRAM/tile 容量及正常/额外模式。

## xdelta3 与可复现性

发布工具从源码构建 ROM，再调用外部 xdelta3，最后解码补丁并逐字节对比。初始补丁使用官方 xdelta3 **3.2.2**，参数 `-a -e -9 -S none -A -D`：禁用新 armor、二级压缩和应用文件名头，保留经典 VCDIFF 与窗口校验。

包装工具对 3.0/3.1 不传仅 3.2 支持的 `-a`。不同 xdelta 版本的编码优化可能产生不同补丁字节；同一源码的 ROM 必须一致，若要求补丁本身一致也应固定工具版本。工具清除环境变量 `XDELTA`，避免本机隐含参数改变产物。

## 回退与发布

```sh
# 只在另存的测试副本上回到原版；不会覆盖主构建产物。
mkdir -p build
cp KirbyDreamLand_CHS-Monado.gb build/rollback-test.gb
bash ROLLBACK.sh --base baserom.gb --target build/rollback-test.gb

# 源码修订的回退使用 Git 历史。
git revert <commit>
```

每次发布检查：符号化改动面与清单一致（`python tools/change_surface.py check --base baserom.gb`）、
源码重建目标哈希一致、补丁重放一致、错误输入被拒绝、回退副本恢复原版、输入未变、暂存区无 ROM/存档/模拟器/临时文件。发布补丁不发布 ROM。公开 CI 只运行公开资源与合成样本测试；本地自备 ROM 测试单独记录。

## 可复用维护任务模板

```text
请在本仓库修订[页面/条目]，使用 source/manifest.json 指定的 Rev 1 输入。
保持[未改动部分]不变，修改[目标字形/位置/资源]。
同步更新实际构建资源、核稿文本或素材、版本清单、测试和 CHANGELOG。
运行源码构建与 xdelta3 重放并核验哈希；原版及输出 ROM 均保持 gitignore。
保留 Rev 1 程序修复及输入校验，不复用旧版地址；提交补丁而非 ROM。
```
