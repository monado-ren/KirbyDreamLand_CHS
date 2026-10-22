# 00_Tools — 构建、验证与编辑工具

这里放全部可执行工具；`tools` 是指向本目录的兼容符号链接，旧命令 `python tools/...` 继续有效。

- `build.py` / `verify.py` / `release.py` / `apply_patch.py` / `rollback.py`
- `change_surface.py`：符号化改动面的派生、校验、asm 审阅
- `pages.py` / `page_edits.py`：整页 PNG 与“基线+覆盖层”页
- `audit_pages.py` / `audit_visual_regression.py`：静态预算与运行时截图核对
- `fetch_fonts.py` / `build_rgbds.py`：从 pinned 上游源生成字体、从源码编译 RGBDS
- `capture_pages.py` / `analyze_playthrough.py`：用 PyBoy 驱动 ROM 抓取整屏状态、分析游玩过程
- `record_review_videos.py`：基于打过 `sameboy_gui_capture.patch` 的 SameBoy 前端录制全流程演示视频
- `sameboy_capture.c` / `sameboy_gui_capture.patch`：SameBoy 无头驱动与 SDL 前端捕获补丁
- `hal_codec.py` / `graphics_png.py` / `common.py`：编解码与公共逻辑

依赖：`requirements.txt`（Pillow）、`requirements-dev.txt`（字体生成）、可选 RGBDS（`build_rgbds.py`）、xdelta3（发布/回滚）。
