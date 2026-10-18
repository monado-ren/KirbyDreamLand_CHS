# 符号化改动面（source/change_surface.json）

v0.5.1 相对日版 Rev 1 的全部改动（110 处原银行补丁、198 字节，71 个扩展资源）原先只以
`expected_hex` / `replacement_hex` 存在于 `source/manifest.json`。本文件把同一改动面提升为
**语义层**：每处补丁都有装载点名称、目标资源、旧值→新值、用途说明和历史原因。

```
source/change_surface.json   47 个装载点/代码补丁 + 71 个资源（46 活跃 + 25 历史副本）
tools/change_surface.py      check / explain / resources / dump
tests/test_change_surface.py 符号层必须精确派生出清单
```

**发布清单仍是构建权威。** 符号层不参与直接构建，而是被校验为与清单逐字节一致：
`tools/build.py`、`tools/verify.py`、`tools/selftest.py` 在使用默认 `source/manifest.json` 时都会强制核对；
公开测试也会核对。这样 ROM 哈希不变，同时改动面可用人话审阅。

## 结构

```jsonc
{
  "header": {
    "rom_size_code": {"offset": "0x00148", "old": 3, "new": 4},
    "checksums": {"policy": "recompute", "excluded_from_global": ["0x014E", "0x014F"]}
  },
  "resources": [
    {"id": "rom_041000", "label": "normal_hud", "role": "active",
     "purpose": "普通模式 HUD 字形条", "format": "sheet",
     "bank": 16, "offset": "0x041000", "capacity": 259}
  ],
  "sites": [
    {"site": "normal_hud_load", "kind": "loader.sheet", "resource": "rom_041000",
     "purpose": "普通 HUD 图块装载点（原代码重复 5 处，每处 2 字节）",
     "patches": [
       {"offset": "0x01B44", "kind": "loader.source_addr", "old": "0x4855",
        "new": {"resource": "rom_041000", "field": "cpu_address"}},
       {"offset": "0x01B4A", "kind": "loader.bank", "old": 2,
        "new": {"resource": "rom_041000", "field": "bank"}}
     ]}
  ]
}
```

### 补丁 kind

| kind | 长度 | 含义 |
| --- | --- | --- |
| `loader.source_addr` | 2 | 装载源地址（小端）；新值由资源的 `offset/bank` 派生 |
| `loader.bank` | 1 | 装载源 bank；新值由资源 `bank` 派生 |
| `loader.vram_base` | 1 | 装载目的高字节（`0x98→0x88` 标题/配置，`0x98→0x90` 关卡与失败页） |
| `stage.pointer_table` | 15 | 5 关三字节指针表，按 `{stage, old/new:{bank,addr}, resource}` 结构化 |
| `hud.label_tile` | 1 | HUD 标签图块号重排 |
| `sprite.x` | 1 | 图鉴第 4 页蝙蝠精灵专用 X 坐标 |
| `rom.size` | 1 | MBC1 ROM size code `3→4` |
| `code.region` | 41 | 指令级代码区域：整个例程由 RGBDS 汇编源生成，manifest 补丁是它与 Rev1 的连续差异段 |

`old` 是 Rev 1 原值；`new` 可以是字面值，也可以是 `{"resource": "...", "field": "cpu_address"|"bank"}`
的符号引用。`expected_hex` 由 `old` 编码得到，`replacement_hex` 由 `new` 编码得到，均不需要手写。

## 指令级代码补丁（source/patches）

唯一的游戏逻辑改动是关卡介绍的两行 vblank 写入器（区域 `0x180A0..0x180C8`，bank 6，41 字节）。
它不再以 4 个 hex 块保存，而是一个 `code.region`：

- `source/patches/vblank_two_row.asm`：RGBDS 汇编源，含旧例程反汇编对照与逐行注释；
- 符号层 `region` 里固定 `old_hex`（Rev1 41 字节）、`new_hex`（汇编结果 41 字节）、`runs` 与 `notes`；
- manifest 的 4 处补丁（1 + 10 + 1 + 20 = 32 字节）由 `old_hex`/`new_hex` 的差异段自动派生，不是手写。

外部汇编器只用于**开发期校验/修改**，不参与 stdlib 构建（`new_hex` 已固定，ROM 可复现）：

```sh
# 下载 RGBDS（测试版本 1.0.4）解压到 build/rgbds 或加入 PATH
# https://github.com/gbdev/rgbds/releases
python tools/change_surface.py check --base baserom.gb --rgbds build/rgbds   # ASM=PASS
python tools/change_surface.py assemble --write --rgbds build/rgbds         # 改 asm 后同步 new_hex
```

改代码补丁的流程：编辑 `.asm` → `assemble --write` 更新 `new_hex` → `check`（应仍 PASS，
若改动使 manifest 4 段补丁变化，需要按新版本流程 repack/发布）→ 构建/验证。

## 命令

```sh
# 符号层 == 清单（110 处 / 198 字节 / 47 站点 / 71 资源），并核对 baserom 前置字节与哈希
python tools/change_surface.py check --base baserom.gb

# manifest 的 patches 段由符号层生成（无参数时只校验；--write 重写清单）
python tools/change_surface.py sync-manifest
python tools/change_surface.py sync-manifest --write

# 人话审阅：每个装载点的资源、旧址→新址、代码补丁含义
python tools/change_surface.py explain
python tools/change_surface.py explain --site two_row_vblank_queue_writer

# 资源清单（含 active/legacy 与用途）与派生的清单补丁
python tools/change_surface.py resources
python tools/change_surface.py dump
```

`check` 的保证：

- 派生补丁与 `source/manifest.json` 的 `offset / expected_hex / replacement_hex / field` **逐项相等**，顺序一致；
- 71 个资源 id、label、bank、offset、capacity、active/legacy 角色与清单一致；
- 每个活跃资源至少被一个装载点引用；**历史副本不得被任何装载点引用**；
- 替换字节总数固定 198；ROM size code 为 4；校验和策略为“重算”；
- 给出 `--base` 时，前缀字节与 Rev 1 完全匹配、baserom SHA-256 与声明一致。

## 修改流程

1. 编辑 `source/graphics/` 或 `source/pages/`，按现有流程 `retile` → `repack.py` 生成新版本清单；
2. 同步更新 `source/change_surface.json`：改资源条目的 `bank/offset/capacity/purpose`，
   以及在对应 `sites[].patches[]` 里改 `old/new`（新地址尽量用 `{"resource": ...}` 符号引用）；
3. `python tools/change_surface.py sync-manifest --write` 用符号层重写 manifest 的 patches 段，
   再 `python tools/change_surface.py check --base baserom.gb` 必须 PASS；
4. 再构建、验证、发布。

历史副本（25 个，`role: legacy`）保留只为复现 v0.5.1 ROM 哈希；删除它们会改变 ROM 布局与哈希，
属于新版本决策，不能在符号层“顺手清理”。

## 已知限制

- `code` 补丁仍以十六进制块保存，靠 `note` 字段注释指令含义（目前 4 段、32 字节），没有指令级反汇编；
- 校验和不在补丁列表内：构建在补丁写入后按 Game Boy 规范重算 `0x014D` 与 `0x014E–0x014F`；
- 符号层只覆盖“相对 Rev 1 的改动面”，不替代 `docs/DEVELOPMENT.md` 的构建与页面编辑说明。
