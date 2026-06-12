# Artifact Contract

## Input

- A raw inspection video, or a directory of raw videos.
- Videos should not contain debug overlays or watermarks intended only for review.

## Output

The stable artifact for downstream modeling is:

```text
<output>/<video_stem>_clear_frames/frame_*.jpg
```

The exact image extension can be changed with `--image_ext`, but downstream tools should treat the output folder as an ordered frame sequence.

## Reports

The reports are for audit and debugging:

- `run_manifest.json`: source metadata, parameters, and output paths.
- `frame_report.csv`: quality metrics and selection result for each analyzed frame.
- `selected_frames.txt`: selected source index to output index mapping, with output image `sha256`.
- `summary.json`: compact counts and retention ratios.
- `batch_summary.csv`: one row per video in batch mode.

`run_manifest.json` and `summary.json` separate sampling from quality filtering:

- `source_frames`: total frames reported by the source video.
- `analyzed_candidates`: frames actually inspected after `--scan_fps` / `--max_frames`.
- `selected_frames`: frames written to the clean output sequence.
- `dropped_frames`: analyzed candidates dropped by quality filtering. This is kept as a compatibility alias for `quality_dropped_candidates`.
- `quality_dropped_candidates`: analyzed candidates dropped by quality filtering.
- `sampling_skipped_frames`: source frames not analyzed because of sampling or frame limits.
- `retention_ratio`: `selected_frames / analyzed_candidates`.
- `source_retention_ratio`: `selected_frames / source_frames`.

Downstream quality decisions should use `quality_dropped_candidates` or `retention_ratio`, not `sampling_skipped_frames`.

## Health Pass Conditions

`video-frame-preprocess-health <frame_dir>` must exit 0 and report status `ok` before a frame directory is treated as ready for downstream processing. A passing run means:

- required report files are present;
- `selected_frames.txt` has the expected schema;
- every selected output frame exists;
- selected-frame counts agree across `selected_frames.txt`, `summary.json`, `run_manifest.json`, and actual image files;
- when `sha256` is present, output frame bytes match the recorded hash.

## Non-Goals

This project does not decide presentation pacing. Static-section trimming, fast-motion duplication, and strategy generation should happen in a separate timing component after clean frames are produced.
