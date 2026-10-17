# 第三方与素材权利声明

本项目是《星之卡比 / Hoshi no Kirby / Kirby's Dream Land》Game Boy 日版 Rev 1 的非官方简体中文汉化补丁工程，不是原游戏的开源发行版，与 Nintendo、HAL Laboratory 无隶属或官方认可关系。

## 1. MIT 的适用范围

仓库根目录的 MIT 许可仅适用于本项目独立编写、且有权授权的代码和工程文档。它不重新许可原游戏程序、原作文字、角色、图像、标志、音乐、商标、第三方字体或其可复用字形子集。

仓库不分发基底 ROM、模拟器、运行时或即时存档。构建需使用本地提供且哈希匹配的日版 Rev 1 ROM。补丁和资源改动不改变原作元素的权利归属。

## 2. 游戏派生素材与译文

原作及其标志、角色和美术中的权利归 Nintendo、HAL Laboratory 及各自权利人所有。本项目保留用户最终审定的中文 Logo、背景补全、通关提示与“剧终”牌，用于维护汉化修改；这些图稿中可能仍含原作元素，**不声明为全部原创，也不纳入 MIT 授权**。

`assets/artwork/` 是必要的最终编辑参考，而非原版图像导出集合。`source/resources/` 中供构建使用的图块和贴图可能包含同样的原作派生内容，也不适用 MIT 的代码授权范围。`translations/zh-Hans.json` 中的原作文字及相关翻译单独列示，不以代码许可证重新授权原作文本。

## 3. JPZH Bitmap 12：12px 字形子集

- 分发文件：`assets/fonts/jpzh-bitmap-12.json`，150 个字形。
- 上游：[Z Labs Pixel 12px](https://github.com/Astro-2539/ZLabs-Pixel-12px)，所用字体款式为 M CN。
- 上游版权：Copyright (c) 2023-2025, Astro_2539。
- 字体许可：[SIL Open Font License 1.1 原文](LICENSES/ZLabs-Pixel-12px-OFL.txt)。
- 上游保留字体名称为 `Z工坊/ZLabs`；本项目的位图子集以 **JPZH Bitmap 12** 为派生名称。

子集只提取项目所用字形，保留原始像素；不含原版数字或完整字体文件。上游名称仅用于准确注明来源。上游字体构建代码的许可与字体本身的 OFL 分开，本仓库未复制其构建程序。

## 4. JPZH Bitmap HUD 8：8px 字形子集

- 分发文件：`assets/fonts/jpzh-bitmap-hud-8.json`，5 个字形（含空格）。
- 上游：[Fusion Pixel Font](https://github.com/TakWolf/fusion-pixel-font)，8px Monospaced zh_hans，采用 `2026.09.01` 发行版的字体。
- 上游版权：Copyright (c) 2022, TakWolf。
- 字体许可：[SIL Open Font License 1.1 原文](LICENSES/Fusion-Pixel-OFL.txt)。

同时保留该上游字体发行包携带的四份来源声明：

- [Boutique Bitmap 7x7](LICENSES/Fusion-Pixel-upstream/BoutiqueBitmap7x7-OFL.txt)
- [Galmuri](LICENSES/Fusion-Pixel-upstream/Galmuri-LICENSE.txt)
- [Misaki](LICENSES/Fusion-Pixel-upstream/Misaki-misaki.txt)
- [Miseki Bitmap](LICENSES/Fusion-Pixel-upstream/MisekiBitmap-LICENSE.txt)

六份字体许可文件均逐字节复制，没有删改其中版权、名称或联络信息。OFL 适用于可复用字形数据，不因项目其他代码采用 MIT 而被替换。字体渲染后的图稿与字形数据分别归类；图稿所含游戏元素仍按第 2 节处理。

## 5. 格式研究参考

开发时参考了 [huderlem/kirbydreamland](https://github.com/huderlem/kirbydreamland) 对游戏数据结构及 HAL 压缩格式的说明／反汇编。此仓库不复制该参考仓库的汇编源码、ROM 或归档，也不将其内容重新许可为 MIT。项目中独立编写的资源编解码和补丁工具与参考反汇编分开维护。

## 6. 素材目录与构建边界

`assets/`、`translations/` 是清理后的编辑参考。当前可重现构建以 `source/resources/` 中已编码资源为准，**不宣称从 PNG、字形 JSON 或核稿文本自动渲染全部汉化画面**。更新编辑参考后需另行重新编码和验证资源，再更新补丁。来源哈希及元数据清理记录见 [`assets/manifest.json`](assets/manifest.json)。
