# 可读页面索引（source/pages）

`source/pages/` 共 **48 张 PNG**，对应 `source/graphics/` 的 48 个图块集。页面都是 4 色索引 PNG（灰度 255/170/85/0），GitHub、浏览器、GIMP 均可直接预览和编辑。

三类页面：

| 类型 | 数量 | 页面尺寸 | 含义 |
| --- | --- | --- | --- |
| `tilemap` | 23 | 256×256 | 独立图块集 + 独立 32×32 索引表（图鉴、通关提示） |
| `bundle` | 21 | 256×144 / 256×240 | 单资源 = 图块块 + 地图块，游戏一次性拷入 VRAM（标题、场景介绍、配置、声音测试、GAME OVER、CONTINUE） |
| `sheet` | 4 | 128×16 / 128×112 / 128×48 | 纯图块集画布（HUD、结局精灵、开场装饰） |

编辑页面后运行：

```sh
python tools/pages.py retile source/pages/<id>.png
python tools/repack.py --version <new-version>
```

未编辑的页面 retile 后与原始资源逐字节一致；bundle 页面里显示为横条占位图案的格子引用的是原始 ROM 图块，属于只读区域。图块槽位由游戏加载器固定，新增图案会通过压缩去重腾出槽位。

标记“历史副本”的资源当前不被载入器引用，仅为保持 v0.5.1 发布哈希而保留。

## 背景页（独立图块集 + 32×32 索引表）：23 张

| 页面 PNG | 尺寸 | id | 内容 |
| --- | --- | --- | --- |
| [`rom_048462.png`](../source/pages/rom_048462.png) | 256×256 | `rom_048462` | 黑刺球、飞翅球球、瓦豆鲁迪、瓦豆鲁笃、黑大炮 + 蘑菇林 |
| [`rom_048ab2.png`](../source/pages/rom_048ab2.png) | 256×256 | `rom_048ab2` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_048e5c.png`](../source/pages/rom_048e5c.png) | 256×256 | `rom_048e5c` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_049433.png`](../source/pages/rom_049433.png) | 256×256 | `rom_049433` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_0496d4.png`](../source/pages/rom_0496d4.png) | 256×256 | `rom_0496d4` | 箩箩箩、菈菈菈 + 城堡 |
| [`rom_049bf8.png`](../source/pages/rom_049bf8.png) | 256×256 | `rom_049bf8` | 蛙镜鱼、石像怪、乌贼怪、圆锥寄居蟹、光束贝 + 树林 |
| [`rom_049eaf.png`](../source/pages/rom_049eaf.png) | 256×256 | `rom_049eaf` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_04a3a1.png`](../source/pages/rom_04a3a1.png) | 256×256 | `rom_04a3a1` | 疯狂鬼面、膨胀云、晕晕怪、尖耳怪、弯刀骑士 + 城市 |
| [`rom_04a6f0.png`](../source/pages/rom_04a6f0.png) | 256×256 | `rom_04a6f0` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_04ab1b.png`](../source/pages/rom_04ab1b.png) | 256×256 | `rom_04ab1b` | 喔喔鸡、振翅球球、蛋糕怪 + 树林 |
| [`rom_04afee.png`](../source/pages/rom_04afee.png) | 256×256 | `rom_04afee` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_04b4db.png`](../source/pages/rom_04b4db.png) | 256×256 | `rom_04b4db` | 章鱼怪、暴躁石像、独眼蟹、连射炮 + 海与船 |
| [`rom_04b943.png`](../source/pages/rom_04b943.png) | 256×256 | `rom_04b943` | 子弹鹈鹕、胡须猫、武魔、本尼 + 星空 |
| [`rom_04bcd1.png`](../source/pages/rom_04bcd1.png) | 256×256 | `rom_04bcd1` | 图鉴页（早期版本，保留以维持发布哈希） ·历史副本 |
| [`rom_04c4f4.png`](../source/pages/rom_04c4f4.png) | 256×256 | `rom_04c4f4` | 喳喳鸟、蘑菇怪、头带熊、小波比兄弟 + 山丘 |
| [`rom_04caf2.png`](../source/pages/rom_04caf2.png) | 256×256 | `rom_04caf2` | 振翅蝙蝠、绿海葵、芒比尸、魔扫把、两面派、吐舌箱、惊吓幽灵 + 城堡 |
| [`rom_04cd98.png`](../source/pages/rom_04cd98.png) | 256×256 | `rom_04cd98` | 卡钸拉 + 云 |
| [`rom_04d0bb.png`](../source/pages/rom_04d0bb.png) | 256×256 | `rom_04d0bb` | 独眼云 + 星空 |
| [`rom_04d586.png`](../source/pages/rom_04d586.png) | 256×256 | `rom_04d586` | 睡帽幽灵、冒出箱、P瓜先生、骷髅头 + 砖墙 |
| [`rom_04d918.png`](../source/pages/rom_04d918.png) | 256×256 | `rom_04d918` | 帝帝帝大王 + 王冠舞台 |
| [`rom_055050.png`](../source/pages/rom_055050.png) | 256×256 | `rom_055050` | 额外模式通关提示（★额外 游戏 / ♡恭喜 通关！…） |
| [`rom_056110.png`](../source/pages/rom_056110.png) | 256×256 | `rom_056110` | 普通模式通关提示（★配置 模式 / 送您一份特别的礼物…） |
| [`rom_0742b3.png`](../source/pages/rom_0742b3.png) | 256×256 | `rom_0742b3` | 大波比兄弟、风语大树（双页布局） |

## Bundle 页（单资源 = 图块 + 地图）：21 张

| 页面 PNG | 尺寸 | id | 内容 |
| --- | --- | --- | --- |
| [`rom_040000.png`](../source/pages/rom_040000.png) | 256×144 | `rom_040000` | 标题画面（中文 Logo + 菜单文字） ·历史副本 |
| [`rom_041206.png`](../source/pages/rom_041206.png) | 256×144 | `rom_041206` | 场景 1 介绍页（旧版本） ·历史副本 |
| [`rom_04190d.png`](../source/pages/rom_04190d.png) | 256×144 | `rom_04190d` | 场景 2 介绍页（旧版本） ·历史副本 |
| [`rom_041f98.png`](../source/pages/rom_041f98.png) | 256×144 | `rom_041f98` | 场景 3 介绍页（旧版本） ·历史副本 |
| [`rom_04266d.png`](../source/pages/rom_04266d.png) | 256×144 | `rom_04266d` | 场景 4 介绍页（旧版本） ·历史副本 |
| [`rom_042d5d.png`](../source/pages/rom_042d5d.png) | 256×240 | `rom_042d5d` | 场景 5 介绍页（旧版本） ·历史副本 |
| [`rom_0433c5.png`](../source/pages/rom_0433c5.png) | 256×144 | `rom_0433c5` | 配置页（旧版本） ·历史副本 |
| [`rom_0438f6.png`](../source/pages/rom_0438f6.png) | 256×144 | `rom_0438f6` | 声音测试页面 |
| [`rom_044000.png`](../source/pages/rom_044000.png) | 256×144 | `rom_044000` | 配置页（旧版本） ·历史副本 |
| [`rom_04454c.png`](../source/pages/rom_04454c.png) | 256×144 | `rom_04454c` | GAME OVER 画面 |
| [`rom_044734.png`](../source/pages/rom_044734.png) | 256×144 | `rom_044734` | CONTINUE 画面 |
| [`rom_05c000.png`](../source/pages/rom_05c000.png) | 256×144 | `rom_05c000` | 配置页（声音测试/水平调整/操作说明） |
| [`rom_060000.png`](../source/pages/rom_060000.png) | 256×144 | `rom_060000` | 标题画面（中文 Logo + 菜单文字） ·历史副本 |
| [`rom_064000.png`](../source/pages/rom_064000.png) | 256×144 | `rom_064000` | 场景 1 介绍页（场景1 / 葛绿谷绿） ·历史副本 |
| [`rom_0646fa.png`](../source/pages/rom_0646fa.png) | 256×144 | `rom_0646fa` | 场景 2 介绍页（场景2 / 箩箩箩的城堡） ·历史副本 |
| [`rom_06c000.png`](../source/pages/rom_06c000.png) | 256×144 | `rom_06c000` | 场景 1 介绍页（场景1 / 葛绿谷绿） |
| [`rom_06c70b.png`](../source/pages/rom_06c70b.png) | 256×144 | `rom_06c70b` | 场景 2 介绍页（场景2 / 箩箩箩的城堡） |
| [`rom_06cda8.png`](../source/pages/rom_06cda8.png) | 256×144 | `rom_06cda8` | 场景 3 介绍页（场景3 / 漂浮岛屿） |
| [`rom_06d490.png`](../source/pages/rom_06d490.png) | 256×144 | `rom_06d490` | 场景 4 介绍页（场景4 / 泡泡云层） |
| [`rom_06db85.png`](../source/pages/rom_06db85.png) | 256×240 | `rom_06db85` | 场景 5 介绍页（场景5 / 帝帝帝山） |
| [`rom_070000.png`](../source/pages/rom_070000.png) | 256×144 | `rom_070000` | 标题画面（中文 Logo + 菜单文字） |

## 图块画布页（纯图块集）：4 张

| 页面 PNG | 尺寸 | id | 内容 |
| --- | --- | --- | --- |
| [`rom_041000.png`](../source/pages/rom_041000.png) | 128×16 | `rom_041000` | 普通模式 HUD 字形条（分/卡/比/积、数字、图标） |
| [`rom_041103.png`](../source/pages/rom_041103.png) | 128×16 | `rom_041103` | 额外模式 HUD 字形条 |
| [`rom_050000.png`](../source/pages/rom_050000.png) | 128×112 | `rom_050000` | 结局/通关提示精灵表 |
| [`rom_058000.png`](../source/pages/rom_058000.png) | 128×48 | `rom_058000` | 开场装饰图块 |
