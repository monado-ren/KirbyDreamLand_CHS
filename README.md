# 星之卡比 GB · 简体中文汉化补丁

基于 **Hoshi no Kirby (Japan) (Rev 1)**（日版 1.1）的汉化补丁工程。
当前版本 **v0.5.1**，保留 Rev 1 程序修正，含场景 5 两行文字上移 2 像素的调整。

本仓库提供构建源码、汉化资源及 **xdelta3 补丁**，不提供原版或汉化版 ROM。
本版本为部分汉化；演职人员表及游戏内汉化署名尚未接入，详见 [完成情况](docs/STATUS.md)。

## 输入 ROM

请自行准备原始日版 Rev 1 文件，放在仓库根目录并命名为 **`baserom.gb`**。
文件名不是版本依据，工具会验证大小及以下三个哈希，任何一项不匹配即停止。

| 项目 | 值 |
| --- | --- |
| 原始文件名 | `Hoshi no Kirby (Japan) (Rev 1).gb` |
| 大小 | `262144` 字节 |
| SHA-256 | `c4c6aff6242116c4f26bdcf3343b6c27836010853b8753da8b0cb953a200834a` |

## 从源码构建

需要 **Python 3.11+** 与 [Pillow](https://python-pillow.org/)（PNG 编解码；版本见 `requirements.txt`）：

```sh
python -m pip install -r requirements.txt
python 00_Tools/build_rgbds.py     # 从 pinned 源码编译 RGBDS（代码补丁汇编/校验需要）
```

构建并生成补丁还需要 [xdelta3](https://github.com/jmacd/xdelta/releases) 命令行工具；将其加入 PATH，或通过 `--xdelta` 指定路径。

```sh
# 构建 ROM 并生成、重放验证 xdelta3 补丁
python 00_Tools/release.py

# xdelta3 未加入 PATH 时
python 00_Tools/release.py --xdelta /path/to/xdelta3

# 仅从源码构建 ROM（不需要 xdelta3）
python 00_Tools/build.py
python 00_Tools/verify.py
```

产物均位于仓库根目录：

| 产物 | Git 策略 |
| --- | --- |
| `baserom.gb` | 用户输入，忽略，保持不变 |
| `KirbyDreamLand_CHS-Monado.gb` | 构建结果，忽略 |
| `patches/KirbyDreamLand_CHS-Monado.xdelta3` | 相对于 `baserom.gb` 的构建结果，**提交版本管理**（根目录同名符号链接为兼容入口） |

v0.5.1 输出为 **524288 字节**，与开发工程的 `kirby_jp_rev1_zh_v0.5.1_stage5_up2.gb` 逐字节一致：

```text
SHA-256 f96fe0ecac53cc586eac19b53fe1b50cef3fd1751261ae273c2356b2c6c62795
```

## 直接应用补丁

```sh
python 00_Tools/apply_patch.py
# 或原生 xdelta3 命令（输入须先按上表核验）
xdelta3 -d -s baserom.gb patches/KirbyDreamLand_CHS-Monado.xdelta3 KirbyDreamLand_CHS-Monado.gb
python 00_Tools/verify.py
```

Python 包装工具在写入前校验输入和重建结果；若已有同名输出，请先另存需要保留的版本。

## 维护与目录

```text
00_Tools/        构建、验证、HAL/PNG 编解码、页面、审计、字体/RGBDS 工具
01_Export/       导出/溯源入口（实际 provenance 在 03_Image/edits、04_Data、06_ProgramFix）
02_Text/         核稿文本与接入状态（非自动渲染输入）
03_Image/        graphics（构建权威）、pages（21 张整页 PNG）、edits（27 个基线+覆盖层）、artwork
04_Data/         manifest.json（71 资源/布局/哈希）、assets.json
05_Font/         pinned 上游字体与生成说明（字形 JSON gitignored）
06_ProgramFix/   change_surface.json + patches/*.asm（补丁唯一符号来源）
patches/         发布 xdelta3 补丁
00_Tools/           -> 00_Tools
02_Text/    -> 02_Text
tests/           可公开重跑的工具测试
docs/            开发方法、地址约束、页面/预算/运行时报告
LICENSES/        第三方字体许可和署名
```

编号目录是真实内容；旧命令中的 `tools/` 已改为 `00_Tools/`，`translations/` 已改为 `02_Text/`。
详见 [工序目录](docs/PIPELINE.md) 与 [图片/字体来源](docs/IMAGE_PROVENANCE.md)。

构建不读取旧日版、美版、旧汉化 ROM、模拟器或开发者本机目录。
今后的汉化修订在本仓库提交；请同时更新源码资源、版本清单、补丁与测试。
[页面索引](docs/PAGES.md) 列出全部 48 个页面及其内容（21 张整页 PNG + 27 个基线+覆盖层页面）。`02_Text/` 与 `assets/` 是编辑素材，**仅编辑这些文件不会自动重排整个游戏**；真正参与构建的是 `03_Image/graphics/` 下的 PNG 源，详见 [开发说明](docs/DEVELOPMENT.md)；改动面的语义索引见 [符号化改动面](docs/CHANGE_SURFACE.md)，分层构成见 [改动面构成](docs/CHANGE_SURFACE_COMPOSITION.md)。

```sh
python -m unittest discover -s tests -v
python 00_Tools/selftest.py
python 00_Tools/change_surface.py check --base baserom.gb
python 00_Tools/change_surface.py summary
python 00_Tools/change_surface.py explain
python 00_Tools/change_surface.py sync-manifest
# 编辑用字形子集不随仓库分发，从上游 pinned 源生成（需要 requirements-dev.txt）
python -m pip install -r requirements-dev.txt
python 00_Tools/fetch_fonts.py
# 代码补丁的指令级源在 06_ProgramFix/patches/*.asm，清单加载时会用 RGBDS 汇编
python 00_Tools/change_surface.py check --base baserom.gb
python 00_Tools/audit_public_tree.py
# 将 PNG 派生的实际字节导出到 gitignored 的 build/resources/ 供比对
python 00_Tools/derive_resources.py

# 整页编辑：重新生成/校验可读页面，或把编辑过的页面拆回图块集+索引表
python 00_Tools/pages.py render
python 00_Tools/pages.py render --check
python 00_Tools/page_edits.py render             # 基线+覆盖层页重建到 gitignored 的 build/pages/
python 00_Tools/pages.py retile build/pages/rom_048462.png   # 编辑后回写图块集/地图并刷新覆盖层
```

原创工具代码及有权授权的文档采用 [MIT](LICENSE)。游戏及派生美术、字体不被重新授权为 MIT，参见 [第三方与资源声明](THIRD_PARTY_NOTICES.md)。本项目为非官方汉化项目。
