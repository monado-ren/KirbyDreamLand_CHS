# 图片与字体的来源：哪些是字体排版，哪些是人工修图

本仓库**没有逐 tile 的来源字段**；下面按页面/资源归类，依据是：

- `04_Data/assets.json` 的 artwork 描述（“最终稿 / 手工补全 / 8px 中文排版”）；
- `docs/STATUS.md`：“HUD 与通关提示使用 8×8 字形；关卡名、菜单、图鉴等使用 12 像素字形”；
- `03_Image/edits/*.json` 的 changed cells（人工改动面）；
- `docs/PAGES.md`、`docs/CHANGELOG.md` 的历史修订记录。

“字体渲染”指用 12px / 8px 位图字形**手工排版/生成**的文字像素；当前仓库并不保存
“译文 + 字体 + 布局 → 自动重排”的源码，只保存结果页面/覆盖层。

## 字体排版部分（12px 字形）

| 页面/图片 | 字体排版内容 | 备注 |
| --- | --- | --- |
| `03_Image/pages/rom_070000.png`（标题） | 标题菜单、“额外游戏”等文字 | Logo 不是字体（见下） |
| `03_Image/pages/rom_05c000.png`（配置） | 配置项/按钮文字 | 背景是人工图 |
| `03_Image/pages/rom_0438f6.png`（声音测试） | 声音测试文字 | 背景/图标沿用原版或混合 |
| `03_Image/pages/rom_06c000/06c70b/06cda8/06d490/06db85.png`（场景 1–5 介绍） | “场景 1–5”关卡标题 | 背景/角标见下 |
| `03_Image/pages/rom_04454c.png`（GAME OVER） | “游戏结束”等文字 | 背景沿用/混合 |
| `03_Image/pages/rom_044734.png`（CONTINUE） | “继续”等文字 | 背景沿用/混合 |
| 14 张图鉴页（`03_Image/edits/rom_048462…rom_0742b3`） | 图鉴名称、类型/说明排版 | 角色/背景是原版或人工修订 |
| `03_Image/edits/rom_055050`、`rom_056110`（通关提示） | 8px 中文提示文本 | 手柄插图/背景另计 |
| `03_Image/edits/rom_041000`、`rom_041103`（HUD） | “得分/额外”等 8px 标签 | 数字、图标沿用原版 |

配套的“字体排版最终稿”图：

- `03_Image/artwork/ending-hint-normal.png`
- `03_Image/artwork/ending-hint-extra.png`

这两张本身就是 8px 中文排版稿，不是手绘插画。

## 人工修图部分

以下文件是**人工像素画/手绘/人工补背景**（不是字体渲染）：

| 文件 | 用途 |
| --- | --- |
| `03_Image/artwork/title-logo.png` | 标题中文 Logo 最终稿 |
| `03_Image/artwork/corner-logo.png` | 场景介绍右下角中文角标（也对应 `rom_058000` 开场装饰图块） |
| `03_Image/artwork/configuration-background.png` | 配置页中文平铺背景 |
| `03_Image/artwork/ending-sign.png` | 结尾“剧终”牌（也用于 `rom_050000` 结局精灵表） |
| `03_Image/artwork/stage-01-background.png` | 第 1 关背景手工补全 |
| `03_Image/artwork/stage-02-background.png` | 第 2 关背景手工补全 |
| `03_Image/artwork/gallery-03-background.png` | 图鉴第 3 页第 2 次修订背景 |

另外，以下改动属于**人工像素修图/排版**，但只以页面覆盖层形式存在，没有单独的 artwork 原图：

- 图鉴页的角色位置/背景修订（例：振翅蝙蝠页专用精灵左移 9 像素）；
- 图鉴页用户核准的背景修订（保留最终稿的只有 `gallery-03-background.png`，其余以 `03_Image/edits/*.json` + 覆盖层为准）；
- 部分页面的角标/装饰/精灵位置微调。

## 原版沿用、未重新绘制

- 场景 3–5 的背景（未列入手工补全）；
- 图鉴页大部分角色/精灵（除用户明确改过的背景/位置）；
- HUD 数字、图标；
- 通关提示中的手柄插图（文字是 8px 排版，插图沿用/混合）；
- 演职人员表（未汉化，原版滚动画面）。

## 判断规则（维护时）

- 改**文字**：先找该页是 12px 还是 8px；从 `05_Font/generated` 取字形重新排版，或直接改页面 PNG，然后 `00_Tools/pages.py retile`。
- 改**美术**：以 `03_Image/artwork/*.png` 为最终稿来源；没有 artwork 原图的页面，直接改 `03_Image/pages/*.png` 或对应覆盖层。
- 改完必须重跑 `pages.py render --check`、`page_edits.py check`、`audit_pages.py --check` 和构建哈希验证。
