# 符号化改动面（06_ProgramFix/change_surface.json）

> 分层总览与数字构成见 [改动面构成](CHANGE_SURFACE_COMPOSITION.md)。

v0.5.1 相对日版 Rev 1 的全部改动（110 处补丁、198 字节，71 个扩展资源）以语义层
`06_ProgramFix/change_surface.json` 为源：装载点名称、目标资源、旧值→新值、用途、历史副本原因、
校验和策略，以及代码区域的 RGBDS 汇编源。

**仓库不再存储补丁 hex。** `04_Data/manifest.json` 只保留资源/布局和一个派生摘要
`change_surface.sha256`；加载清单时由符号层派生出 110 处补丁（代码区域用 RGBDS 汇编），
并与摘要核对。因此改动面可用人话审阅，漂移仍会被检测。

```
06_ProgramFix/change_surface.json        47 个装载点/代码补丁 + 71 个资源（46 活跃 + 25 历史副本）
06_ProgramFix/patches/vblank_two_row.asm 本地化后的代码区域（RGBDS）
06_ProgramFix/patches/vblank_two_row.rev1.asm  Rev1 基线代码区域（RGBDS，用于派生 preimage）
00_Tools/change_surface.py           check / explain / resources / dump / sync-manifest
00_Tools/build_rgbds.py              从 pinned 源码下载并编译 RGBDS 到 build/rgbds
```

## 结构

```jsonc
{
  "header": {"rom_size_code": {"offset": "0x00148", "old": 3, "new": 4},
             "checksums": {"policy": "recompute", "excluded_from_global": ["0x014E","0x014F"]}},
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
     ]},
    {"site": "two_row_vblank_queue_writer", "kind": "code.region",
     "region": {"offset": "0x180A0", "length": 41, "bank": 6,
                "asm_rev1": "06_ProgramFix/patches/vblank_two_row.rev1.asm",
                "asm": "06_ProgramFix/patches/vblank_two_row.asm",
                "notes": ["...", "..."]},
     "patches": []}
  ]
}
```

### 补丁 kind

| kind | 长度 | 含义 |
| --- | --- | --- |
| `loader.source_addr` | 2 | 装载源地址（小端）；新值由资源 `offset/bank` 派生 |
| `loader.bank` | 1 | 装载源 bank；新值由资源 `bank` 派生 |
| `loader.vram_base` | 1 | 装载目的高字节（`0x98→0x88` 标题/配置，`0x98→0x90` 关卡与失败页） |
| `stage.pointer_table` | 15 | 5 关三字节指针表，按 `{stage, old/new:{bank,addr}, resource}` 结构化 |
| `hud.label_tile` | 1 | HUD 标签图块号重排 |
| `sprite.x` | 1 | 图鉴第 4 页蝙蝠精灵专用 X 坐标 |
| `rom.size` | 1 | MBC1 ROM size code `3→4` |
| `code.region` | 区域 | 指令级代码：`asm_rev1` 与 `asm` 各汇编一次，差异段自动成为 manifest 补丁（当前 41 字节区域 → 4 段 / 32 字节） |

`old` 是 Rev 1 原值；`new` 可以是字面值，也可以是 `{"resource": "...", "field": "cpu_address"|"bank"}`
的符号引用。代码区域没有 hex 字段：旧/新字节都由 RGBDS 从汇编源生成。

## 命令

```sh
python 00_Tools/build_rgbds.py                     # 首次/更新：从 pinned 源码编译 RGBDS
python 00_Tools/change_surface.py check --base baserom.gb
python 00_Tools/change_surface.py summary      # 分层构成（补丁/资源/页面/文本层）
python 00_Tools/change_surface.py explain
python 00_Tools/change_surface.py explain --site two_row_vblank_queue_writer
python 00_Tools/change_surface.py resources
python 00_Tools/change_surface.py dump
python 00_Tools/change_surface.py sync-manifest          # 只校验派生摘要
python 00_Tools/change_surface.py sync-manifest --write  # 写入 digest（清单不存补丁 hex）
```

`check` 的保证：

- 由符号层派生 110 处补丁（198 字节），摘要与 `04_Data/manifest.json` 的
  `change_surface.sha256` 一致；
- `asm_rev1` 与 `asm` 都能被 RGBDS 汇编，旧汇编字节与用户提供的 Rev1 前置字节一致；
- 71 个资源 id、label、bank、offset、capacity、active/legacy 角色与清单一致；
- 每个活跃资源至少被一个装载点引用；历史副本不得被任何装载点引用；
- ROM size code 为 4；校验和策略为“重算”。

## 修改流程

1. 编辑 `03_Image/graphics/`、`03_Image/pages/`（21 张 bundle 页）或 `build/pages/`（27 个基线+覆盖层页），
   按现有流程 `retile` → `repack.py` 生成新版本清单；
2. 改动代码补丁时编辑 `06_ProgramFix/patches/*.asm`；改动加载/指针时更新 `06_ProgramFix/change_surface.json` 的
   资源条目或 `sites[].patches[]`；
3. `python 00_Tools/change_surface.py sync-manifest --write` 更新清单里的派生摘要；
4. `python 00_Tools/change_surface.py check --base baserom.gb` 必须 PASS；
5. 再构建、验证、发布。

历史副本（25 个，`role: legacy`）保留只为复现 v0.5.1 ROM 哈希；删除它们会改变 ROM 布局与哈希，
属于新版本决策，不能在符号层“顺手清理”。

## RGBDS

- 版本钉在 `00_Tools/build_rgbds.py`：`RGBDS v1.0.4`，源码 tarball SHA-256 固定；
- 脚本下载、校验、用 `make` 编译，把 `rgbasm/rgblink/rgbfix/rgbgfx` 放进 gitignored 的 `build/rgbds`；
- 需要 C++ 工具链与 `make`；仓库不提交 RGBDS 源码或二进制。

## 已知限制

- 校验和不在补丁列表内：构建在补丁写入后按 Game Boy 规范重算 `0x014D` 与 `0x014E–0x014F`；
- `change_surface.sha256` 只覆盖派生补丁列表；资源像素由各资源的 `decoded_sha256` 与构建摘要保护；
- 符号层只覆盖“相对 Rev 1 的改动面”，不替代 `docs/DEVELOPMENT.md` 的构建与页面编辑说明。
