# video-frame-preprocess

[English](README.md) | [中文](README.zh-CN.md)

`video-frame-preprocess` 是一个独立的本地 Python package，用于把原始巡检视频转换成可供后续点云建模流程使用的干净帧序列。

它只负责视频前处理：抽帧、质量评估、模糊/曝光/对比度过滤、保守丢帧控制和本地报告输出。它不负责静止段删帧、快速移动段补帧、重建训练、上传数据或修改图像内容。

## 功能

- 处理单个视频或视频目录。
- 支持全帧扫描或按 `--scan_fps` 采样扫描。
- 使用清晰度、亮度和对比度过滤明显低质量帧。
- 用 `--max_drop_ratio` 和 `--max_consecutive_drops` 控制过度丢帧风险。
- 输出干净帧、manifest、质量报告、摘要和可选过滤后视频。
- 提供 `video-frame-preprocess-health` 检查输出产物完整性。
- 提供 `video-frame-preprocess-demo` 生成确定性 demo 视频。

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

## 批处理

```bash
video-frame-preprocess-batch --config src/video_frame_preprocess/config/default.json
```

默认配置读取 `input/` 下的视频，输出到 `outputs/`。

## 健康检查

```bash
video-frame-preprocess-health outputs/demo_clear_frames
```

机器可读输出：

```bash
video-frame-preprocess-health outputs/demo_clear_frames --json
```

健康检查会确认：

- 必需报告文件存在；
- `selected_frames.txt` schema 正确；
- 每个选中帧文件存在；
- `summary.json`、`run_manifest.json`、实际图像文件和 selected frame 记录数量一致；
- `selected_frames.txt` 中的 `sha256` 和输出图像字节一致。

## 输出

核心输出目录：

```text
outputs/<video_stem>_clear_frames/
  frame_000000_src_000000.jpg
  selected_frames.txt
  run_manifest.json
  frame_report.csv
  summary.json
```

下游建模默认只消费 `frame_*` 图像序列。报告文件用于审计和排查。

统计字段会区分采样和质量过滤：

- `source_frames`：源视频总帧数；
- `analyzed_candidates`：实际分析的候选帧数量；
- `selected_frames`：写出的干净帧数量；
- `quality_dropped_candidates` / `dropped_frames`：已分析候选帧中被质量过滤丢弃的数量；
- `sampling_skipped_frames`：因为采样或帧数上限未分析的源视频帧；
- `retention_ratio`：`selected_frames / analyzed_candidates`；
- `source_retention_ratio`：`selected_frames / source_frames`。

## 与 frame-timing-skill 的关系

推荐链路：

```text
raw video
  -> video-frame-preprocess
  -> clean_frames
  -> frame-timing-skill
  -> modeling-ready frames
  -> reconstruction
```

`frame-timing-skill` 应消费本项目输出的干净帧目录。静止段删帧、快速移动段重复帧和 timing strategy 不属于本项目。
