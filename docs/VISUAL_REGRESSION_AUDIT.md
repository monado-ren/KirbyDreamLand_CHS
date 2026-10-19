# 外部 BGB 视觉回归包 → 页面源核对

由 `PYTHONPATH=build/pylibs python 00_Tools/audit_visual_regression.py --write` 生成。

- 包内 ROM SHA-256：`4591cc4a3b584cc4ea7735aff1e65899c5bd7fc252b95daa34c4948d1e6ca486`（与当前构建一致）
- 模拟器：BGB 1.6.6；画面数：32；缺失画面：无
- 原生重载校验：True；屏幕/内存/退出状态一致：True
- 包内逐像素核验：PASS（31 个静态画面，714240 像素，差异 0；1 个动态附加画面排除）
- 页面覆盖：30/30 个活跃页面被此包覆盖；缺失：无

## 逐屏核对

| 画面 | 说明 | 期望页面 | 地图匹配 | tile 匹配 | 地图来源 | 动态差异 | 状态 |
| --- | --- | --- | ---: | ---: | --- | ---: | --- |
| `configuration` | 配置模式 | `rom_05c000` | 0.984 | 1.000 | bgmap | 9 | PASS_DYNAMIC |
| `continue` | CONTINUE／继续选择 | `rom_044734` | 1.000 | 1.000 | bgmap | - | PASS |
| `credits_bonus` | 演职人员表（附加） | - | - | - | - | - | NOT_LOCALIZED |
| `ending_sign` | 剧终牌 | `rom_050000` | 0.000 | 1.000 | - | - | PASS |
| `gallery_01` | 图鉴第 01 页：黑刺球、瓦豆鲁迪、飞翅球球、瓦豆鲁笃、黑大炮 | `rom_048462` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_02` | 图鉴第 02 页：喳喳鸟、头带熊、蘑菇怪、小波比兄弟 | `rom_04c4f4` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_03` | 图鉴第 03 页：大波比兄弟、风语大树 | `rom_0742b3` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_04` | 图鉴第 04 页：振翅蝙蝠、绿海葵、芒比尸、魔扫把、两面派、吐舌箱、惊吓幽灵 | `rom_04caf2` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_05` | 图鉴第 05 页：箩箩箩、菈菈菈 | `rom_0496d4` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_06` | 图鉴第 06 页：蛙镜鱼、石像怪、乌贼怪、圆锥寄居蟹、光束贝 | `rom_049bf8` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_07` | 图鉴第 07 页：卡钸拉 | `rom_04cd98` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_08` | 图鉴第 08 页：膨胀云、疯狂鬼面、尖耳怪、晕晕怪、弯刀骑士 | `rom_04a3a1` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_09` | 图鉴第 09 页：独眼云 | `rom_04d0bb` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_10` | 图鉴第 10 页：喔喔鸡、振翅球球、蛋糕怪 | `rom_04ab1b` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_11` | 图鉴第 11 页：P瓜先生、睡帽幽灵、冒出箱、骷髅头 | `rom_04d586` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_12` | 图鉴第 12 页：章鱼怪、暴躁石像、独眼蟹、连射炮 | `rom_04b4db` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_13` | 图鉴第 13 页：子弹鹈鹕、胡须猫、本尼、武魔 | `rom_04b943` | 1.000 | 1.000 | bgmap | - | PASS |
| `gallery_14` | 图鉴第 14 页：帝帝帝大王 | `rom_04d918` | 1.000 | 1.000 | bgmap | - | PASS |
| `game_over` | GAME OVER／游戏结束 | `rom_04454c` | 1.000 | 1.000 | bgmap | - | PASS |
| `hint_extra` | 额外游戏通关提示 | `rom_056110` | 1.000 | 1.000 | bgmap | - | PASS |
| `hint_normal` | 普通游戏通关提示 | `rom_055050` | 1.000 | 1.000 | bgmap | - | PASS |
| `hud_extra` | 额外游戏内 HUD | `rom_041103` | 0.000 | 1.000 | - | - | PASS |
| `hud_normal` | 普通游戏内 HUD | `rom_041000` | 0.000 | 1.000 | - | - | PASS |
| `main_menu` | 主菜单／额外游戏已解锁标题 | `rom_070000` | 1.000 | 1.000 | bgmap | - | PASS |
| `opening_decoration` | 开场装饰资源引用 | `rom_058000` | 0.000 | 1.000 | - | - | PASS |
| `sound_test` | 声音测试 | `rom_0438f6` | 0.998 | 1.000 | bgmap | 1 | PASS_DYNAMIC |
| `stage_1_intro` | 场景 1：葛绿谷绿 | `rom_06c000` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_2_intro` | 场景 2：箩箩箩的城堡 | `rom_06c70b` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_3_intro` | 场景 3：漂浮岛屿 | `rom_06cda8` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_4_intro` | 场景 4：泡泡云层 | `rom_06d490` | 1.000 | 1.000 | bgmap | - | PASS |
| `stage_5_intro` | 场景 5：帝帝帝山 | `rom_06db85` | 1.000 | 1.000 | bgmap | - | PASS |
| `title` | 标题画面 | `rom_070000` | 1.000 | 1.000 | bgmap | - | PASS |

## 问题

- 无。

## 说明

- 地图匹配取 `bgmap.bin`、VRAM `0x9800`、VRAM `0x9C00` 三个来源中的最佳值；标题页允许纵向滚动偏移。
- tile 匹配：bundle 页优先按该页 loader 目的地址比较，其次在 VRAM 中搜索该页 tile 块；tilemap 页搜索 tileset 前缀；sheet 页搜索完整图块块。
- `credits_bonus` 是未汉化的原版演职人员表滚动画面，不对应任何本地化页面，包内也标记为动态（非静态逐像素核验）。
- `configuration` / `sound_test` 的地图差异是菜单光标/选项高亮在页面加载后写入 BG map 造成的动态格子，tile 块仍精确匹配，因此标为 `PASS_DYNAMIC`。
- `hint_normal` 是普通模式通关后的提示页（提示如何进入额外模式），对应 `rom_055050`；`hint_extra` 是额外模式通关后的提示页（提示如何进入配置模式），对应 `rom_056110`。`change_surface.json` 的 purpose 已按此修正。
- `title` 与 `main_menu` 都是 `rom_070000`；`opening_decoration` 是 `stage_1_intro` 的别名捕获，检查的是同一状态下的角标图块。
- sheet 页（HUD/角标/剧终牌）没有独立的 BG map 可比较，只看整块 tile 是否出现在 VRAM。
- 本报告只核对包的外观数据与页面源；BGB 原生 `state.sna` 不随仓库分发。
