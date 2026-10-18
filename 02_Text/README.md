# 02_Text — 文本与审稿

当前内容为 `zh-Hans.json`：121 条审稿记录，其中 84 条已接入、37 条明确未汉化。

**注意：`translations` 是审稿参考，不是自动渲染输入。** 本仓库的构建读取的是
`../03_Image/graphics/*.png`（以及页面/覆盖层）；仅修改这里的译文不会改变 ROM。

## 文本层（font + translation → page）

已为可直接精确匹配的页面建立文本层：

- `layout.json`：每条文本的页面、字体（12px）、行高、(x, y) 锚点；
- `../03_Image/text-base/<page>.png`：同一页面去掉文字墨迹后的底图；
- `00_Tools/text_layout.py`：`extract` 从现有页面反解布局，`check` 验证
  `base + font(translation, layout)` 与页面逐像素一致，`render --write` 重新生成页面。

当前覆盖 8 个页面 / 11 条文本（场景 1–5 关卡名、声音测试、GAME OVER、CONTINUE）。
改译文后运行：

```sh
python 00_Tools/text_layout.py render --write   # 由底图+字体+译文重排页面
python 00_Tools/pages.py retile 03_Image/pages/<page>.png
python 00_Tools/repack.py --version v0.5.2
```

其他页面（配置、标题、图鉴、通关提示）的文字仍是人工排版的像素，或含边框/背景穿插，
暂未纳入文本层；它们继续按页面 PNG / 覆盖层维护。
