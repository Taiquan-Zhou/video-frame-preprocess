# Video Frame Preprocess

[English](README.md) | [中文](README.zh-CN.md)

Video Frame Preprocess is a local Python package and agent-friendly preprocessing step for converting raw inspection videos into clean frame sequences. It runs before `frame-timing-skill`: this project extracts and quality-filters frames; `frame-timing-skill` handles timing changes later.

It does not delete static sections, duplicate fast-motion frames, run reconstruction, upload data, or modify image content beyond writing decoded output frames.

## Features

- Extract frames from one video or a video directory.
- Filter obvious bad frames using sharpness, brightness, and contrast.
- Keep filtering conservative with drop-ratio and consecutive-drop safeguards.
- Write clean frames, manifests, reports, summaries, and optional filtered videos.
- Verify outputs with `video-frame-preprocess-health`.
- Generate a deterministic demo video with `video-frame-preprocess-demo`.

## For Users

### Use As An Agent Skill

Ask your AI coding agent to use this repository before `frame-timing-skill` when the input is raw video:

```text
Use video-frame-preprocess on path/to/raw_video.mp4.
Then pass the clean frame directory to frame-timing-skill.
```

Expected flow:

```text
raw video -> video-frame-preprocess -> clean_frames -> frame-timing-skill -> reconstruction-ready frames
```

## For Developers

### Install Python Package

```bash
python -m pip install git+https://github.com/Taiquan-Zhou/video-frame-preprocess.git
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

### CLI Usage

Create a demo video:

```bash
video-frame-preprocess-demo --output input/demo.mp4
```

Process one video:

```bash
video-frame-preprocess \
  --video input/demo.mp4 \
  --output outputs/demo_clear_frames \
  --selection quality_filter \
  --scan_fps 0 \
  --image_ext jpg \
  --clean
```

Check the output:

```bash
video-frame-preprocess-health outputs/demo_clear_frames
```

Batch mode:

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

## Output Contract

The downstream-safe output is the clean frame directory:

```text
outputs/<video_stem>_clear_frames/
  frame_000000_src_000000.jpg
  selected_frames.txt
  run_manifest.json
  frame_report.csv
  summary.json
```

Pass only the `frame_*` images to downstream reconstruction by default. Reports are for audit and debugging. `selected_frames.txt` includes `sha256`, and `video-frame-preprocess-health` verifies frame bytes against it.

## Development Checks

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
python -m compileall -q src tests
python -m build
```

For detailed artifact rules, see `docs/artifact-contract.md`.
