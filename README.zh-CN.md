# Video Frame Preprocess

[English](README.md) | [中文](README.zh-CN.md)

Video Frame Preprocess 是一个本地 Python 包，也是 Agent 友好的预处理步骤，用于把原始巡检视频转换成干净帧序列。它位于 `frame-timing-skill` 之前：本项目负责抽帧和质量过滤，`frame-timing-skill` 后续负责帧时序调整。

它不删除静止段、不重复快速移动段帧、不执行重建、不上传数据，也不会修改图像内容，只会写出解码后的输出帧。

## 功能

- 从单个视频或视频目录抽帧。
- 基于清晰度、亮度和对比度过滤明显低质量帧。
- 用丢帧比例和连续丢帧保护保持保守过滤。
- 输出干净帧、manifest、报告、摘要和可选过滤后视频。
- 使用 `video-frame-preprocess-health` 校验输出产物。
- 使用 `video-frame-preprocess-demo` 生成确定性 demo 视频。

## For Users

### Use as an Agent Skill

当输入是原始视频时，让你的 AI coding agent 在 `frame-timing-skill` 之前安装并使用这个仓库：

```text
Install this skill: https://github.com/Taiquan-Zhou/video-frame-preprocess
```

然后对视频运行：

```text
Use video-frame-preprocess on path/to/raw_video.mp4.
Then pass the clean frame directory to frame-timing-skill.
```

推荐流程：

```text
raw video -> video-frame-preprocess -> clean_frames -> frame-timing-skill -> reconstruction-ready frames
```

## For Developers

### Install Python Package

```bash
python -m pip install git+https://github.com/Taiquan-Zhou/video-frame-preprocess.git
```

本地开发：

```bash
python -m pip install -e ".[dev]"
```

### CLI Usage

生成 demo 视频：

```bash
video-frame-preprocess-demo --output input/demo.mp4
```

处理单个视频：

```bash
video-frame-preprocess \
  --video input/demo.mp4 \
  --output outputs/demo_clear_frames \
  --selection quality_filter \
  --scan_fps 0 \
  --image_ext jpg \
  --clean
```

检查输出：

```bash
video-frame-preprocess-health outputs/demo_clear_frames
```

批处理：

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

## Output Contract

下游安全使用的产物是干净帧目录：

```text
outputs/<video_stem>_clear_frames/
  frame_000000_src_000000.jpg
  selected_frames.txt
  run_manifest.json
  frame_report.csv
  summary.json
```

默认只把 `frame_*` 图像交给下游重建流程。报告文件用于审计和排查。`selected_frames.txt` 包含 `sha256`，`video-frame-preprocess-health` 会校验输出图像字节。

## Development Checks

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
python -m compileall -q src tests
python -m build
```

更详细的产物规则见 `docs/artifact-contract.md`。
