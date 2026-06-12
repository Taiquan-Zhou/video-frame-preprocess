# Usage

## Install

```bash
python -m pip install .
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

## Single Video

Create a deterministic local demo video:

```bash
video-frame-preprocess-demo --output input/demo.mp4
```

```bash
video-frame-preprocess \
  --video input/test1.mp4 \
  --output outputs/test1_clear_frames \
  --selection quality_filter \
  --scan_fps 0 \
  --sharpness_quantile 0.10 \
  --max_drop_ratio 0.08 \
  --max_consecutive_drops 2 \
  --image_ext jpg \
  --jpg_quality 95 \
  --filtered_video outputs/test1_filtered_clean.mp4 \
  --clean
```

Use `--scan_fps 0` when you want to inspect every source frame before quality filtering.

## Batch

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

The default config expects raw videos in `input/` and writes artifacts under `outputs/`.

## Health Check

```bash
video-frame-preprocess-health outputs/test1_clear_frames
```

JSON output:

```bash
video-frame-preprocess-health outputs/test1_clear_frames --json
```

A passing health check means:

- required report files are present;
- `selected_frames.txt` has the expected schema;
- every selected frame path exists;
- recorded frame `sha256` values match output image bytes;
- selected-frame counts agree across manifest, summary, and actual frame files.

## Downstream Flow

Pass the clean frame directory to timing or reconstruction tools:

```text
raw video
  -> video-frame-preprocess
  -> outputs/<video_stem>_clear_frames
  -> frame-timing-skill
  -> modeling-ready frames
```

Do not pass audit videos, preview videos, CSV reports, or analysis files to reconstruction models as image input.
