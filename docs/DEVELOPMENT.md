# 构建与后续修订

## 唯一输入与构建方式

只接受仓库根目录的 `baserom.gb`（日本 Rev 1、256 KiB）。源码构建的全部输入为它及 `source/`；不依赖旧 ROM、成品 ROM、旧开发工程或第三方 Python 库。

`source/manifest.json` 声明版本、三个输入/输出哈希、原银行修改的前置字节、扩展资源地址、银行号、容量、原始和压缩摘要。构建步骤：

1. 核验输入大小及 MD5 / SHA-1 / SHA-256。
2. 以原版字节为底，扩容至 512 KiB，空白区填 `FF`。
3. 校验 110 段局部补丁前置字节后写入，共 198 个原银行字节；校验和另算。
4. 将 71 份 `source/resources/*.bin`（共 150560 字节的 2bpp 图形/地图数据）重新 HAL 压缩，按清单写入。逐条验证大小、摘要、解压往返、银行边界及不重叠。
5. 重算 Game Boy 头部和全局校验和，检查最终三个哈希及保留的 Rev 1 修复。

71 份资源包括 25 份当前载入器未引用的旧资源，清单已标注。这些字节仍存在于既定 v0.5.1 中，为保证与指定成品 **Hash 一致**而保留，不应擅自清零。

## 文件不是完整反汇编工程

`source/resources/` 是实际参与构建的未压缩游戏图形/地图格式，而不是整份 ROM 的改名或封装。原版代码和未改动数据来自用户的输入。

`translations/` 和 `assets/` 提供核稿文本及编辑参考。当前工具不自动将全部译文、PNG、字体重排为游戏页面；修改它们后必须同步修改对应 raw tile/map 资源、指针或新增编译接口，再进行验证。

## 修改一份既有 raw 资源

先用清单的 `label`、`offset`、`bank`、`cpu_address`、当前引用状态定位正确版本。例如场景 5 当前包位于 ROM `0x6DB85`，源为 `source/resources/r_06db85.bin`。

以下流程适用于维持 raw 长度、分配地址和容量的资源修改：

```sh
git switch -c codex/my-localization-change
# 编辑对应 source/resources/*.bin；同时更新译文/美术参考与测试。
python tools/repack.py --version v0.5.2-dev.1
python tools/build.py --manifest build/manifest.edited.json --output build/check.gb
python tools/verify.py --manifest build/manifest.edited.json --rom build/check.gb --base baserom.gb
python tools/release.py --manifest build/manifest.edited.json --output build/check.gb --patch build/check.xdelta3
```

`repack.py` 默认生成独立开发清单 `build/manifest.edited.json`，保留已发布清单；常规构建会拒绝未登记的资源变化。压缩结果超出分配容量、改变 raw 长度或需要移动指针的修改，应先扩展清单与对应构建/测试，不能靠截断数据处理。

审核通过后，将开发清单的完整内容作为新的 `source/manifest.json`，使用新版本号，更新 `CHANGELOG.md` 和目标哈希，再运行 `python tools/release.py`。新源码资源、清单与命名 xdelta3 补丁在同一提交中更新。原版的三个输入哈希保持不变。

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
