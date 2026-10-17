# 编辑参考素材

本目录对应日版 Rev 1 汉化 **v0.5.1**，仅保留当前采用的字形及最终审定图稿，不收录原版资源全集、模拟器截图、旧稿或字体安装文件。

## 与构建流程的关系

发布构建以 `source/resources/` 中的资源数据为准。这里的 PNG 和字形 JSON 是供人工编辑、核对的参考素材；修改它们或 `translations/zh-Hans.json` **不会自动重绘、编码或更新 ROM**。编辑后的素材还需要单独完成四级灰度映射、图块分配、贴图编码、资源更新和运行时验证。

`manifest.json` 记录尺寸、SHA-256 与权利类别。图片已去除 XMP、ICC、DPI 等非像素元数据，输出 PNG 的 RGBA 像素与所选最终输入逐像素相同；没有缩放、重新描绘或平滑处理。标题和图鉴背景选用项目已经验证的 Game Boy 四级灰度稿，其余图稿保留核准输入的像素；不要将任意 RGB 灰度直接当成 ROM 色号。

## 字形

| 文件 | 内容 | 许可 |
| --- | --- | --- |
| `fonts/jpzh-bitmap-12.json` | 150 个字形：原有 148 字加“额”“外”；12 像素高，拉丁字母 P 为 6 像素宽 | OFL-1.1 |
| `fonts/jpzh-bitmap-hud-8.json` | HUD 的空格、分、卡、比、积，共 5 个 8×8 字形 | OFL-1.1 及附带上游声明 |

两份子集使用中立的派生名称 **JPZH Bitmap**。上游名称只用于来源说明，不表示上游为本项目背书。每行 `0` 表示背景、`1` 表示字形墨色；字形逐像素保留，不含抗锯齿。数字继续使用基底 ROM 的原有字形，因此不在这里重复分发。8px 通关提示的最终排版在图稿中保留；没有将整套 8px 字体打包进仓库。

## 最终图稿

| 文件 | 尺寸 | 用途 |
| --- | --- | --- |
| `artwork/title-logo.png` | 160×120 | 标题 Logo 最终稿 |
| `artwork/corner-logo.png` | 32×16 | 场景页右下角 Logo |
| `artwork/configuration-background.png` | 160×144 | 配置页中文背景 |
| `artwork/ending-sign.png` | 32×32 | “剧终”牌 |
| `artwork/ending-hint-normal.png` | 160×144 | 普通通关提示 |
| `artwork/ending-hint-extra.png` | 160×144 | 额外模式通关提示 |
| `artwork/stage-01-background.png` | 160×144 | 第 1 关补全背景 |
| `artwork/stage-02-background.png` | 160×144 | 第 2 关补全背景 |
| `artwork/gallery-03-background.png` | 160×144 | 大波比兄弟／风语大树页的最终背景 |

图稿可能包含原作图形、标志及其修改内容，**不适用项目代码的 MIT 许可**。详见 [第三方声明](../THIRD_PARTY_NOTICES.md)。六份字体许可原文位于 [LICENSES](../LICENSES/)；manifest 中的许可哈希用于核对原文未被改写。
