# patches — 发布补丁

- `KirbyDreamLand_CHS-Monado.xdelta3`：相对 `baserom.gb` 的官方发布增量，已提交版本管理。
- 根目录的同名文件是兼容符号链接；新路径以本目录为准。
- 校验：`SHA256SUMS.txt`；应用：`python tools/apply_patch.py` 或原生 `xdelta3 -d -s baserom.gb patches/KirbyDreamLand_CHS-Monado.xdelta3 KirbyDreamLand_CHS-Monado.gb`。

`baserom.gb`、构建产物 ROM 和模拟器存档都不入库。
