# video-frame-preprocess

[English](README.md) | [中文](README.zh-CN.md)

`video-frame-preprocess` 是一个独立的视频预处理工具，用于点云重建工作流。它从原始巡检视频中抽取帧，过滤明显低质量帧，并输出可复现、可审计的报告，供后续帧时序优化和建模使用。

它位于 `frame-timing-skill` 之前：

```text
raw video
  -> video-frame-preprocess
  -> clean_frames/
  -> frame-timing-skill
  -> modeling-ready frames
  -> reconstruction
```

## 功能

- 处理单个视频或视频目录。
- 支持全帧抽取，也支持通过 `--scan_fps` 采样扫描。
- 基于清晰度、亮度和对比度过滤低质量帧。
- 通过 `--max_drop_ratio` 和 `--max_consecutive_drops` 限制过度丢帧。
- 输出干净帧、manifest、质量报告、摘要和可选过滤后视频。
- 使用 `video-frame-preprocess-health` 校验输出产物。
- 使用 `video-frame-preprocess-demo` 生成确定性 demo 视频。

本项目不处理静止段删帧、快速移动段重复帧等帧时序策略；这些步骤属于 `frame-timing-skill`。

## 安装

```bash
python -m pip install .
```

开发模式：

```bash
python -m pip install -e ".[dev]"
```

## Demo

```bash
video-frame-preprocess-demo --output input/demo.mp4
```

## 单视频处理

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

使用 `--scan_fps 0` 可以在质量过滤前检查每个源视频帧。

## 批处理

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

默认配置从 `input/` 读取视频，并将结果写入 `outputs/`。

## 健康检查

```bash
video-frame-preprocess-health outputs/demo_clear_frames
```

机器可读输出：

```bash
video-frame-preprocess-health outputs/demo_clear_frames --json
```

健康检查通过表示：

- 必需报告文件存在；
- `selected_frames.txt` schema 正确；
- 每个选中输出帧都存在；
- `selected_frames.txt`、`summary.json`、`run_manifest.json` 和实际图像文件中的帧数量一致；
- 记录的 `sha256` 与输出图像字节一致。

## 输出

下游安全使用的核心产物是帧目录：

```text
outputs/<video_stem>_clear_frames/
  frame_000000_src_000000.jpg
  selected_frames.txt
  run_manifest.json
  frame_report.csv
  summary.json
```

默认只把清洗后的 `frame_*` 图像交给重建流程。报告文件用于审计和排查。

## 统计字段

`run_manifest.json` 和 `summary.json` 会区分采样和质量过滤：

- `source_frames`：源视频报告的总帧数；
- `analyzed_candidates`：经过 `--scan_fps` 或 `--max_frames` 后实际分析的帧；
- `selected_frames`：写入干净帧序列的帧；
- `quality_dropped_candidates` / `dropped_frames`：质量过滤丢弃的已分析候选帧；
- `sampling_skipped_frames`：因为采样或帧数上限未分析的源视频帧；
- `retention_ratio`：`selected_frames / analyzed_candidates`；
- `source_retention_ratio`：`selected_frames / source_frames`。

## 开发检查

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
python -m compileall -q src tests
python -m build
```
