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
| MD5 | `995ce81fe91162cff295badd94e366f3` |
| SHA-1 | `5fe35fab25299b6c53b40decfe2b1827b4a64d2a` |
| SHA-256 | `c4c6aff6242116c4f26bdcf3343b6c27836010853b8753da8b0cb953a200834a` |

## 从源码构建

需要 **Python 3.10+**（仅标准库）。构建并生成补丁还需要 [xdelta3](https://github.com/jmacd/xdelta/releases) 命令行工具；将其加入 PATH，或通过 `--xdelta` 指定路径。

```sh
# 构建 ROM 并生成、重放验证 xdelta3 补丁
python tools/release.py

# xdelta3 未加入 PATH 时
python tools/release.py --xdelta /path/to/xdelta3

# 仅从源码构建 ROM（不需要 xdelta3）
python tools/build.py
python tools/verify.py
```

产物均位于仓库根目录：

| 产物 | Git 策略 |
| --- | --- |
| `baserom.gb` | 用户输入，忽略，保持不变 |
| `KirbyDreamLand_CHS-Monado.gb` | 构建结果，忽略 |
| `KirbyDreamLand_CHS-Monado.xdelta3` | 相对于 `baserom.gb` 的构建结果，**提交版本管理** |

v0.5.1 输出为 **524288 字节**，与开发工程的 `kirby_jp_rev1_zh_v0.5.1_stage5_up2.gb` 逐字节一致：

```text
MD5     8b88da8006dd245bcecf87ee1d65b2c8
SHA-256 f96fe0ecac53cc586eac19b53fe1b50cef3fd1751261ae273c2356b2c6c62795
```

## 直接应用补丁

```sh
python tools/apply_patch.py
# 或原生 xdelta3 命令（输入须先按上表核验）
xdelta3 -d -s baserom.gb KirbyDreamLand_CHS-Monado.xdelta3 KirbyDreamLand_CHS-Monado.gb
python tools/verify.py
```

Python 包装工具在写入前校验输入和重建结果；若已有同名输出，请先另存需要保留的版本。

## 维护与目录

```text
source/         原银行补丁声明、71 份可重新压缩的图形资源及构建清单
tools/          独立构建、HAL 编解码、修订封装、xdelta3、校验工具
translations/   核稿文本与接入状态
assets/         选定的用户修订素材、可复用字形及来源信息
tests/          可公开重跑的工具测试
docs/           开发方法、地址约束、发布状态
LICENSES/       第三方字体许可和署名
```

构建不读取旧日版、美版、旧汉化 ROM、模拟器或开发者本机目录。
今后的汉化修订在本仓库提交；请同时更新源码资源、版本清单、补丁与测试。
译文和 PNG 是编辑素材，**仅编辑这些文件不会自动重排整个游戏**；真正参与构建的是 `source/`，详见 [开发说明](docs/DEVELOPMENT.md)。

```sh
python -m unittest discover -s tests -v
python tools/selftest.py
python tools/audit_public_tree.py
```

原创工具代码及有权授权的文档采用 [MIT](LICENSE)。游戏及派生美术、字体不被重新授权为 MIT，参见 [第三方与资源声明](THIRD_PARTY_NOTICES.md)。本项目为非官方汉化项目。
