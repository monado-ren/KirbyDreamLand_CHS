# 改动面构成（v0.5.1 相对日版 Rev 1）

本文件回答“这个项目到底改了哪些面、各占多少”，是 [`CHANGE_SURFACE.md`](CHANGE_SURFACE.md)
的总览版。所有数字可由下面命令复算：

```sh
python 00_Tools/change_surface.py summary
```

当前输出：

```text
SURFACE=PASS PATCHES=110 BYTES=198 SITES=47 RESOURCES=71 PAGES=48 ACTIVE_PAGES=30 TEXT_LAYER=11/8
```

## 1. 分层总览

| 层 | 规模 | 存储位置 | 作用 |
| --- | --- | --- | --- |
| 容器/头部 | 1 处补丁 / 1 B + 校验和重算 | `06_ProgramFix/change_surface.json` 的 `header` | 256→512 KiB，MBC1 size code `3→4`；`0x014D`、`0x014E–0x014F` 由构建重算 |
| 代码区域 | 1 个 site / 41 B 区域 → 4 段 / 32 B | `06_ProgramFix/patches/vblank_two_row*.asm` | VBlank 两行队列写入循环，RGBDS 汇编、差异段自动成为补丁 |
| 装载器/指针 | 41 个 loader site + 5 个特殊 site / 100 + 15 + 4 B | `change_surface.json` 的 `sites` | 把资源重定向到扩展 bank、改 VRAM 基址、改关卡指针表、HUD/精灵微调 |
| 资源 | 71 个（46 活跃 + 25 历史副本） | `04_Data/manifest.json` + `03_Image/graphics/*.png` | 新增/替换的压缩图块集、地图、整包页；活跃包 44,760 B / 容量 156,669 B |
| 页面/图形 | 48 页（21 bundle PNG + 27 覆盖层页） | `03_Image/pages/`、`03_Image/edits/` | 30 个活跃页 + 18 个 v0.5.1 复现用历史页；92 张 PNG 源 |
| 文本 | 121 条（84 已接入 / 37 未汉化） | `02_Text/zh-Hans.json` | 审稿文本；其中 11 条 / 8 页已由字体+译文+布局生成 |
| 字库/美术 | 12px 150 字形 + 8px 56 字形；9 张最终图稿 | `05_Font/`、`03_Image/artwork/` | 字形从 pinned 上游生成（gitignored）；Logo/背景/剧终牌是人工图 |
| 发布 | ROM 512 KiB / 32 bank；xdelta3 34,852 B | `patches/`、`SHA256SUMS.txt` | 相对 `baserom.gb` 的发布增量，字节级可复现 |

## 2. 补丁字节构成（110 处 / 198 B）

| kind | 数量 | 字节 | 占比 | 内容 |
| --- | ---: | ---: | ---: | --- |
| `loader.source_addr` | 46 | 92 | 46.5% | 装载源地址（小端 2 B），新值由资源 `offset/bank` 派生 |
| `loader.bank` | 48 | 48 | 24.2% | 装载源 bank，新值由资源 `bank` 派生 |
| `code.region` | 4 | 32 | 16.2% | VBlank 代码差异段（41 B 区域中的 4 段） |
| `stage.pointer_table` | 1 | 15 | 7.6% | 5 关三字节指针表（5×3 B） |
| `loader.vram_base` | 6 | 6 | 3.0% | 装载目的高字节：标题/配置 `0x98→0x88`，关卡/失败页 `0x98→0x90` |
| `hud.label_tile` | 3 | 3 | 1.5% | HUD 标签图块号重排，使“得分”左对齐 |
| `rom.size` | 1 | 1 | 0.5% | MBC1 ROM size code `3→4` |
| `sprite.x` | 1 | 1 | 0.5% | 图鉴第 4 页蝙蝠专用 X 坐标 `F8→EF`（-9 px） |
| **合计** | **110** | **198** | **100%** | 另有 3 B 校验和由构建重算，不计入补丁 |

按改动动机归类：

| 动机 | 字节 | 说明 |
| --- | ---: | --- |
| 装载器重定向 | 100 | 41 个 loader site（16 tileset + 16 tilemap + 5 bundle + 4 sheet）的源地址/bank/VRAM 基址 |
| 代码修复 | 32 | VBlank 队列写入由 1 行改 2 行 |
| 指针表 | 15 | 5 个关卡整包入口 |
| 文本/UI 微调 | 4 | HUD 标签 3 B + 蝙蝠 X 1 B |
| 容器扩容 | 1 | ROM size code |

## 3. 资源层（71 = 46 活跃 + 25 历史副本）

| 格式 | 数量 | 活跃 | 历史副本 | 活跃 packed B | 活跃 capacity B |
| --- | ---: | ---: | ---: | ---: | ---: |
| bundle | 21 | 10 | 11 | 16,137 | 65,982 |
| tileset | 23 | 16 | 7 | — | — |
| tilemap | 23 | 16 | 7 | — | — |
| sheet | 4 | 4 | 0 | — | — |
| **合计** | **71** | **46** | **25** | **44,760** | **156,669** |

- 活跃资源分布在 bank 16–23、27–29；历史副本占用 bank 16–19、24、25。
- 25 个历史副本（28,510 B packed / 56,323 B capacity）只为**复现 v0.5.1 ROM 哈希**保留，当前加载器不引用；删除它们会改变布局与哈希，属于新版本决策。
- 19 个活跃页面资源 `capacity == packed_size`（零余量），见 `docs/PAGE_BUDGET.md`。

## 4. 页面/图形层（48 页）

| 存储方式 | 总数 | 活跃 | 历史副本 | 说明 |
| --- | ---: | ---: | ---: | --- |
| `page`（整页 PNG） | 21 | 10 | 11 | 标题、配置、声音测试、GAME OVER、CONTINUE、5 关介绍 |
| `edit`（基线+覆盖层） | 27 | 20 | 7 | 图鉴 14 页、2 张通关提示、HUD、结局精灵、开场装饰 |
| **合计** | **48** | **30** | **18** | 48 页索引见 `docs/PAGES.md` |

- `03_Image/graphics/`：92 张 PNG = 71 个资源图块/地图源 + 21 张 bundle 地图 PNG。
- `03_Image/pages/`：21 张整页 PNG；`03_Image/edits/`：27 个 JSON + 27 张 cells PNG。
- `03_Image/artwork/`：9 张最终图稿（标题 Logo、角标、配置背景、剧终牌、两张 8px 提示排版、2 张关卡补背景、图鉴 3 背景）。

## 5. 文本层（121 条 / 84 已接入）

| 分类 | 条目 |
| --- | ---: |
| gallery | 48 |
| credits | 32（未接入） |
| menu | 13 |
| stage | 10 |
| ending_hint | 8 |
| title | 4 |
| copyright | 3（未接入） |
| hud | 2 |
| ending | 1 |
| **合计** | **121**（integrated 84 / not_localized 37） |

已数据化（可由字体+译文+布局重排）的 11 条 / 8 页：

- 5 个关卡名（葛绿谷绿、箩箩箩的城堡、漂浮岛屿、泡泡云层、帝帝帝山）
- 声音测试、音乐、音效
- 游戏结束
- 继续、结束

其余文字仍是人工排版像素（配置页、标题页、图鉴 14 页、2 张通关提示等），原因见
`docs/IMAGE_PROVENANCE.md`：字形与边框/背景穿插，或当前 pinned 字体与当年排版不完全一致。

## 6. 字库与美术

- 12px 子集：150 字形；8px 子集：56 字形（HUD + 通关提示用字）。
- 字形由 `05_Font/generated/*.json` 从 pinned 上游源生成，不入库；SHA-256 固定。
- 人工图稿 9 张；纯手绘/补背景项：标题 Logo、角标、配置背景、剧终牌、场景 1/2 补背景、图鉴 3 背景。
- 字体渲染项：关卡名/菜单/图鉴名称/提示文字等（详见 `docs/IMAGE_PROVENANCE.md`）。

## 7. 不改 / 保持原版

- 日版演职人员表、游戏内汉化署名：未接入（37 条 not_localized 中的 35 条）。
- 图鉴大部分角色/精灵、HUD 数字与图标、场景 3–5 背景、手柄插图：沿用原版素材。
- 原版 Rev 1 的头部/校验和策略由构建重算，不在符号层存 hex。

## 8. 验证

```sh
python 00_Tools/change_surface.py check --base baserom.gb
python 00_Tools/change_surface.py summary
python 00_Tools/build.py && python 00_Tools/verify.py
python 00_Tools/pages.py render --check
python 00_Tools/page_edits.py check
python 00_Tools/text_layout.py check
python 00_Tools/audit_pages.py --check
python 00_Tools/audit_visual_regression.py
python -m unittest discover -s tests
```

固定值：`PATCHES=110 BYTES=198`、目标 ROM SHA-256 `f96fe0ec…2795`、
`change_surface.sha256 = 219d7545…`、页面 48、活跃页 30、文本层 11/8。
