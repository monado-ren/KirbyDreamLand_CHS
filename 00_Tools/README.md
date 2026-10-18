# 00_Tools — 构建、验证与编辑工具

这里放全部可执行工具；`tools` 是指向本目录的兼容符号链接，旧命令 `python tools/...` 继续有效。

- `build.py` / `verify.py` / `release.py` / `apply_patch.py` / `rollback.py`
- `change_surface.py`：符号化改动面的派生、校验、asm 审阅
- `pages.py` / `page_edits.py`：整页 PNG 与“基线+覆盖层”页
- `audit_pages.py` / `audit_visual_regression.py`：静态预算与外部 BGB 运行时数据核对
- `fetch_fonts.py` / `build_rgbds.py`：从 pinned 上游源生成字体、从源码编译 RGBDS
- `hal_codec.py` / `graphics_png.py` / `common.py`：编解码与公共逻辑

依赖：`requirements.txt`（Pillow）、`requirements-dev.txt`（字体生成）、可选 RGBDS（`build_rgbds.py`）、xdelta3（发布/回滚）。
