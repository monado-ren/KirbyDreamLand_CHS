# 全程游玩运行时抽检（可选）

静态审计（`docs/PAGE_BUDGET.md`）只能证明页面预算，不能证明运行时 VRAM 里真的装着这些页面。
本流程用 PyBoy 记录一次完整游玩，把每个活跃页面的实时 VRAM / BG map 与页面源逐字节对照。

## 准备

- 本机有图形显示（PyBoy 会开一个窗口）；
- `build/pylibs` 里已有 PyBoy（本地调查依赖，不入库）；
- 本地已构建 `KirbyDreamLand_CHS-Monado.gb`（gitignored）。

## 录制

```sh
PYTHONPATH=build/pylibs python tools/play_capture.py
```

窗口打开后正常游玩，脚本每 **30 帧（0.5 秒）** 自动记录一次：
`build/playthrough/cap_XXXXXX.vram`（8 KiB VRAM）、`.oam`、`.png` 截图、`.json` 寄存器元数据。
**不需要手动打标签**——分析器会按 tile/map 字节自动识别页面。

按键（PyBoy 默认）：方向键 = 十字键，`A` = A，`S` = B，`Return` = Start，
`Backspace` = Select，`Esc` = 退出录制。

玩完后按 `Esc`（或关闭窗口），终端出现 `PLAY_CAPTURE=PASS ...`。

## 需要走到的画面

尽量按顺序覆盖；同一画面停留 1 秒以上，保证至少 2 帧捕获：

1. 标题画面（中文 Logo / 菜单）；
2. 配置页、声音测试（如果当前版本可进入）；
3. 场景 1–5 介绍（每关开头）；
4. 游戏内 HUD（普通模式和额外模式各一次）；
5. 故意 GAME OVER，再选 CONTINUE；
6. 图鉴页逐页翻完（48 页里当前装载的 20 页）；
7. 通关结局：剧终牌、普通/额外模式通关提示、结局精灵表。

当前装载的 30 个页面清单见 `docs/PLAYTHROUGH_AUDIT.md` 生成后的覆盖表；不必手动核对，
没玩到的页面会在报告里列为 MISSING。

## 分析

```sh
PYTHONPATH=build/pylibs python tools/analyze_playthrough.py --write
```

输出：

- `docs/PLAYTHROUGH_AUDIT.md`：每个活跃页面的命中次数、首次/最后帧、最佳地图/tile 匹配率；
- 未识别捕获数（转场、游戏过程、精灵/动画覆盖帧通常不精确匹配，不算失败）。

判据：bundle 页要求地图与 tile 块都 ≥ 0.999；tilemap 页要求地图 ≥ 0.995 且 tileset 前缀出现在
VRAM；sheet 页要求整块图块出现在 VRAM。未命中页面要结合捕获截图判断是没玩到还是采帧间隔问题。

## 边界

- 这是模拟器运行时抽检，不替代实机（真实 DMG / flashcart）验证；
- 录制目录和 ROM 都不入库，只提交汇总报告（不含 ROM 像素数据）；
- 如果页面在运行时匹配失败，先检查是否被精灵/窗口/滚动覆盖，再判断是否真的布局错误。
