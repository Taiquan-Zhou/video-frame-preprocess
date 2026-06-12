# video-frame-preprocess

[English](README.md) | [中文](README.zh-CN.md)

## 中文说明

`video-frame-preprocess` 是一个独立的视频前处理组件，用于把原始巡检视频转换成可供点云建模链路继续处理的干净帧序列。

项目只负责：

- 从单个视频或视频目录抽帧；
- 基于模糊、亮度、对比度过滤明显低质量帧；
- 用保守策略限制过度丢帧和连续丢帧；
- 输出帧目录、质量报告、manifest、可选过滤后视频。

项目不负责帧时序策略，例如静止段删帧、快速移动段重复帧。这类处理交给后续独立项目 `frame-timing-skill`。

推荐链路：

```text
raw video
  -> video-frame-preprocess
  -> clean_frames/
  -> frame-timing-skill
  -> modeling-ready frames
  -> LingBot-Map reconstruction
```

安装开发版：

```bash
python -m pip install -e .
```

处理单个视频：

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

批处理：

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

核心输出：

- `outputs/<video_stem>_clear_frames/frame_*.jpg`：下游默认使用的干净帧序列；
- `run_manifest.json`：输入、参数、输出路径和统计信息；
- `frame_report.csv`：每个已分析帧的质量指标和选择状态；
- `selected_frames.txt`：输出帧到源视频帧号的映射；
- `summary.json`：单视频摘要；
- `batch_summary.csv`：批处理摘要。

当使用 `--scan_fps` 或 `--max_frames` 时，manifest 会区分未采样帧和质量丢弃帧：

- `quality_dropped_candidates` / `dropped_frames`：已分析候选帧中被质量过滤丢弃的数量；
- `sampling_skipped_frames`：因为采样或帧数上限没有分析的源视频帧；
- `retention_ratio`：`selected_frames / analyzed_candidates`；
- `source_retention_ratio`：`selected_frames / source_frames`。

---

`video-frame-preprocess` is a standalone video preprocessing component for point-cloud reconstruction workflows. It extracts clean frames from raw videos, filters obvious quality outliers, and writes reproducible reports for downstream modeling.

## Scope

This project handles:

- full-frame or sampled frame extraction;
- blur, brightness, and contrast based frame quality filtering;
- conservative safeguards against excessive or consecutive frame drops;
- selected-frame reports, manifests, preview videos, and batch summaries.

This project intentionally does not handle frame timing edits such as static-section deletion or fast-motion frame duplication. Those steps belong in `frame-timing-skill`, which should consume this tool's cleaned frame output.

## Pipeline

```text
raw video
  -> video-frame-preprocess
  -> clean_frames/
  -> frame-timing-skill
  -> modeling-ready frames
  -> LingBot-Map reconstruction
```

## Install

```bash
python -m pip install -e .
```

## Single Video

Create a deterministic demo video:

```bash
video-frame-preprocess-demo --output input/demo.mp4
```

```bash
video-frame-preprocess \
  --video input/test1.mp4 \
  --output outputs/test1_clean_frames \
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

Use `--scan_fps 0` to keep full source frame cadence before quality filtering.

## Batch

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

The default config expects videos under `input/` and writes outputs under `outputs/`.

## Outputs

For each video, the main downstream-safe artifact is the frame folder:

```text
outputs/<video_stem>_clear_frames/
```

Typical reports include:

- `run_manifest.json`: reproducible run metadata and output paths;
- `frame_report.csv`: per-frame quality metrics and selection state;
- `selected_frames.txt`: source-to-output frame mapping;
- `summary.json`: compact run summary;
- `batch_summary.csv`: batch-level summary when using the batch CLI.

Only the cleaned frame images should be passed to reconstruction by default.

## Health Check

```bash
video-frame-preprocess-health outputs/test1_clear_frames
```

For machine-readable output:

```bash
video-frame-preprocess-health outputs/test1_clear_frames --json
```

A passing health check confirms that required report files exist, selected frame paths are readable, and selected-frame counts agree across `selected_frames.txt`, `summary.json`, `run_manifest.json`, and actual frame files.
When `sha256` is present in `selected_frames.txt`, the health check also verifies output image bytes against the recorded hash.

## Statistics

`run_manifest.json` and `summary.json` separate sampling from quality filtering:

- `source_frames`: total frames reported by the source video;
- `analyzed_candidates`: frames inspected after `--scan_fps` / `--max_frames`;
- `selected_frames`: frames written to the clean sequence;
- `quality_dropped_candidates` / `dropped_frames`: analyzed candidates dropped by quality filtering;
- `sampling_skipped_frames`: source frames not analyzed because of sampling or limits;
- `retention_ratio`: `selected_frames / analyzed_candidates`;
- `source_retention_ratio`: `selected_frames / source_frames`.
