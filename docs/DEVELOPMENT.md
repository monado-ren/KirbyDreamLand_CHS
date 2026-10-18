# 构建与后续修订

## 唯一输入与构建方式

只接受仓库根目录的 `baserom.gb`（日本 Rev 1、256 KiB）。源码构建的全部输入为它及 `source/`；不依赖旧 ROM、成品 ROM、旧开发工程或第三方 Python 库。

`source/manifest.json` 声明版本、三个输入/输出哈希、原银行修改的前置字节、扩展资源地址、银行号、容量、原始和压缩摘要。构建步骤：

1. 核验输入大小及 MD5 / SHA-1 / SHA-256。
2. 以原版字节为底，扩容至 512 KiB，空白区填 `FF`。
3. 校验 110 段局部补丁前置字节后写入，共 198 个原银行字节；校验和另算。
4. 将 71 份 `source/graphics/*.png` 无损派生成 2bpp 图块/图块表字节（共 150560 字节），重新 HAL 压缩并按清单写入。逐条验证 PNG 模式与尺寸、规范配色、派生大小、摘要、解压往返、银行边界及不重叠。
5. 重算 Game Boy 头部和全局校验和，检查最终三个哈希及保留的 Rev 1 修复。

71 份资源包括 25 份当前载入器未引用的旧资源，清单已标注。这些字节仍存在于既定 v0.5.1 中，为保证与指定成品 **Hash 一致**而保留，不应擅自清零。

## 文件不是完整反汇编工程

`source/graphics/` 是实际参与构建的图形源，而不是整份 ROM 的改名或封装：48 份为 4 色索引 PNG 的 2bpp 图块集，23 份为 32×32、8 位灰度的图块索引表，均可无损派生为游戏使用的原始字节。原版代码和未改动数据来自用户的输入。

`translations/` 和 `assets/` 提供核稿文本及编辑参考。当前工具不自动将全部译文、assets/ 图稿或字体重排为游戏页面；修改它们后必须同步修改对应 `source/graphics/*.png`、指针或新增编译接口，再进行验证。

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

### 整页编辑（source/pages）

`source/pages/<id>.png` 是整页合成图，共 48 张，按资源结构分三类：

| 类型 | 数量 | 页面尺寸 | 资源结构 |
| --- | --- | --- | --- |
| `tilemap` | 23 | 256×256 | 独立图块集 + 独立 32×32 索引表（图鉴、通关提示） |
| `bundle` | 21 | 地图宽×8 × 地图高×8 | 单个资源 = 图块块 + 地图块（场景介绍 128+32×18、场景 5 128+32×30、配置 256+32×18、标题 292+32×18 等） |
| `sheet` | 4 | 图块网格 | 纯图块集（HUD、结局精灵、开场装饰）的画布页 |

bundle 页面里，地图字节指向本资源之外（原始 ROM 的 0x8000 区图块）的格子会显示为横条占位图案，并且在 retile 时只读；只有本资源拥有的格子可以编辑。图块槽位数由游戏加载器固定，新增图案通过压缩去重腾出槽位，不会擅自增加加载长度。

编辑页面后运行 `python tools/pages.py retile source/pages/<id>.png`：

- `python tools/pages.py render` 从图块集+索引表重新生成页面；`--check` 只校验页面是否与资源同步（公开测试会做）。
- 编辑页面后运行 `python tools/pages.py retile source/pages/<id>.png`：未改动的格子保留原索引，改动的格子优先复用已有图块，必要时追加新图块；命令会打印所用策略与容量余量。
- 若资源超出原分配容量，retile 会先用更紧凑的编码，并把仍放不下的资源重分配到扩展 ROM 的空闲空间（如 bank 24–29 的空隙），同时自动改写清单中对应的加载指针补丁。输出中的 `RELOCATE=…` 报告新 bank/CPU 地址与改写补丁数；这会改变 ROM 布局与哈希，属于自定义修订，发布前必须重新生成补丁。
- 之后按本节前面的流程运行 `tools/repack.py` 生成开发清单，再构建、验证、发布。
- 限制：使用 `0x8800` 寻址的两页通关提示只能复用可寻址图块或整体压缩重排；指针改写只覆盖清单中已登记的加载点，模拟器/真实硬件验证仍不可省略。

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

每次发布检查：源码重建目标哈希一致、补丁重放一致、错误输入被拒绝、回退副本恢复原版、输入未变、暂存区无 ROM/存档/模拟器/临时文件。发布补丁不发布 ROM。公开 CI 只运行公开资源与合成样本测试；本地自备 ROM 测试单独记录。

## 可复用维护任务模板

```text
请在本仓库修订[页面/条目]，使用 source/manifest.json 指定的 Rev 1 输入。
保持[未改动部分]不变，修改[目标字形/位置/资源]。
同步更新实际构建资源、核稿文本或素材、版本清单、测试和 CHANGELOG。
运行源码构建与 xdelta3 重放并核验哈希；原版及输出 ROM 均保持 gitignore。
保留 Rev 1 程序修复及输入校验，不复用旧版地址；提交补丁而非 ROM。
```
