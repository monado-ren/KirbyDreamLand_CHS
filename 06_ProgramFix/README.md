# 06_ProgramFix — 符号化补丁与程序修复

- `change_surface.json`：47 个 site / 110 处补丁 / 198 字节的唯一符号来源；资源、loader、指针、头部策略都在这里描述；不含补丁 hex。
- `patches/vblank_two_row.asm`：本地化后的 VBlank 41 字节代码区域。
- `patches/vblank_two_row.rev1.asm`：Rev1 基线，用于派生 preimage。

加载 `04_Data/manifest.json` 时由本目录的符号 + asm 派生补丁，并用 manifest 里的
`change_surface.sha256` 核对；改完补丁语义后运行：

```sh
python tools/change_surface.py sync-manifest --write
python tools/change_surface.py check --base baserom.gb
```


