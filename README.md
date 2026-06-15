# video-frame-preprocess

[English](README.md) | [中文](README.zh-CN.md)

`video-frame-preprocess` is a standalone video preprocessing tool for point-cloud reconstruction workflows. It extracts frames from raw inspection videos, filters obvious quality outliers, and writes reproducible reports for downstream timing optimization and modeling.

It runs before `frame-timing-skill` in the pipeline:

```text
raw video
  -> video-frame-preprocess
  -> clean_frames/
  -> frame-timing-skill
  -> modeling-ready frames
  -> reconstruction
```

## Features

- Process a single video or a directory of videos.
- Extract every source frame or sample by `--scan_fps`.
- Filter low-quality frames using sharpness, brightness, and contrast metrics.
- Limit aggressive deletion with `--max_drop_ratio` and `--max_consecutive_drops`.
- Write clean frames, manifests, quality reports, summaries, and optional filtered videos.
- Validate output artifacts with `video-frame-preprocess-health`.
- Generate deterministic demo videos with `video-frame-preprocess-demo`.

This project does not handle frame timing edits such as static-section deletion or fast-motion frame duplication. Those steps belong in `frame-timing-skill`.

## Install

```bash
python -m pip install .
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

## Demo

```bash
video-frame-preprocess-demo --output input/demo.mp4
```

## Single Video

```bash
video-frame-preprocess \
  --video input/demo.mp4 \
  --output outputs/demo_clear_frames \
  --selection quality_filter \
  --scan_fps 0 \
  --sharpness_quantile 0.10 \
  --max_drop_ratio 0.08 \
  --max_consecutive_drops 2 \
  --image_ext jpg \
  --jpg_quality 95 \
  --filtered_video outputs/demo_filtered_clean.mp4 \
  --clean
```

Use `--scan_fps 0` to inspect every source frame before quality filtering.

## Batch

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

The default config expects videos under `input/` and writes outputs under `outputs/`.

## Health Check

```bash
video-frame-preprocess-health outputs/demo_clear_frames
```

Machine-readable output:

```bash
video-frame-preprocess-health outputs/demo_clear_frames --json
```

A passing health check confirms:

- required report files exist;
- `selected_frames.txt` has the expected schema;
- every selected output frame exists;
- selected-frame counts agree across `selected_frames.txt`, `summary.json`, `run_manifest.json`, and actual image files;
- recorded `sha256` values match output image bytes.

## Outputs

The main downstream-safe artifact is the frame directory:

```text
outputs/<video_stem>_clear_frames/
  frame_000000_src_000000.jpg
  selected_frames.txt
  run_manifest.json
  frame_report.csv
  summary.json
```

Only the cleaned `frame_*` images should be passed to reconstruction by default. Reports are for audit and debugging.

## Statistics

`run_manifest.json` and `summary.json` separate sampling from quality filtering:

- `source_frames`: total frames reported by the source video;
- `analyzed_candidates`: frames inspected after `--scan_fps` or `--max_frames`;
- `selected_frames`: frames written to the clean sequence;
- `quality_dropped_candidates` / `dropped_frames`: analyzed candidates dropped by quality filtering;
- `sampling_skipped_frames`: source frames not analyzed because of sampling or frame limits;
- `retention_ratio`: `selected_frames / analyzed_candidates`;
- `source_retention_ratio`: `selected_frames / source_frames`.

## Development Checks

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
python -m compileall -q src tests
python -m build
```
