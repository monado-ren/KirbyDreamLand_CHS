# 05_Font — 字库

编辑用字形不随仓库分发（`05_Font/generated/*.json` 被 gitignore）：

```sh
python -m pip install -r requirements-dev.txt   # kbitfont
python tools/fetch_fonts.py
```

脚本从 pinned 上游源生成：
- ZLabs Pixel 12px M CN `.kbitx`（SHA-256 固定）
- Fusion Pixel 8px Monospaced zh_hans BDF（SHA-256 固定）

生成物只作编辑参考，不参与 `build.py`；构建输入仍是 `03_Image/graphics/*.png`。
