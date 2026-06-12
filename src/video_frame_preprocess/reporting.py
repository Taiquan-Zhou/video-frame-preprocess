"""Report and manifest writers."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from .models import FrameCandidate, QualityThresholds, SelectedFrame
from .quality import quality_score
from .video_io import file_sha256


def write_report(
    report_path: Path,
    candidates: Iterable[FrameCandidate],
    selected: Sequence[SelectedFrame],
    thresholds: QualityThresholds,
) -> None:
    """Write candidate metrics and selection decisions to CSV."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    selected_by_source = {frame.source_index: frame for frame in selected}
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "source_index",
                "selected",
                "output_index",
                "timestamp_sec",
                "sharpness",
                "brightness",
                "contrast",
                "quality_score",
                "output_path",
                "sha256",
                "min_sharpness",
                "min_brightness",
                "max_brightness",
                "min_contrast",
            ]
        )
        for candidate in candidates:
            selected_frame = selected_by_source.get(candidate.index)
            writer.writerow(
                [
                    candidate.index,
                    int(selected_frame is not None),
                    "" if selected_frame is None else selected_frame.output_index,
                    f"{candidate.timestamp_sec:.6f}",
                    f"{candidate.quality.sharpness:.6f}",
                    f"{candidate.quality.brightness:.6f}",
                    f"{candidate.quality.contrast:.6f}",
                    f"{quality_score(candidate, thresholds):.6f}",
                    "" if selected_frame is None or selected_frame.output_path is None else selected_frame.output_path,
                    "" if selected_frame is None or selected_frame.sha256 is None else selected_frame.sha256,
                    f"{thresholds.min_sharpness:.6f}",
                    f"{thresholds.min_brightness:.6f}",
                    f"{thresholds.max_brightness:.6f}",
                    f"{thresholds.min_contrast:.6f}",
                ]
            )


def _selection_stats(*, total_frames: int, analyzed_count: int, selected_count: int) -> dict[str, int | float]:
    quality_dropped_candidates = max(analyzed_count - selected_count, 0)
    sampling_skipped_frames = max(total_frames - analyzed_count, 0)
    retention_ratio = selected_count / analyzed_count if analyzed_count > 0 else 0.0
    source_retention_ratio = selected_count / total_frames if total_frames > 0 else retention_ratio
    return {
        "source_frames": total_frames,
        "analyzed_candidates": analyzed_count,
        "selected_frames": selected_count,
        "dropped_frames": quality_dropped_candidates,
        "quality_dropped_candidates": quality_dropped_candidates,
        "sampling_skipped_frames": sampling_skipped_frames,
        "retention_ratio": retention_ratio,
        "source_retention_ratio": source_retention_ratio,
    }


def write_summary_json(
    summary_path: Path,
    *,
    video_path: Path,
    src_fps: float,
    total_frames: int,
    candidates: Sequence[FrameCandidate],
    selected: Sequence[SelectedFrame],
    thresholds: QualityThresholds,
    target_fps: float,
    scan_fps: float,
) -> None:
    stats = _selection_stats(
        total_frames=total_frames,
        analyzed_count=len(candidates),
        selected_count=len(selected),
    )
    payload = {
        "video": str(video_path),
        "source_fps": src_fps,
        **stats,
        "target_fps": target_fps,
        "scan_fps": scan_fps,
        "thresholds": {
            "min_sharpness": thresholds.min_sharpness,
            "min_brightness": thresholds.min_brightness,
            "max_brightness": thresholds.max_brightness,
            "min_contrast": thresholds.min_contrast,
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_selected_frames_txt(output_path: Path, selected: Sequence[SelectedFrame]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        f.write("output_index\tsource_index\ttimestamp_sec\tpath\tsha256\n")
        for frame in selected:
            path = "" if frame.output_path is None else frame.output_path.as_posix()
            sha256 = frame.sha256
            if sha256 is None and frame.output_path is not None and frame.output_path.is_file():
                sha256 = file_sha256(frame.output_path)
            f.write(f"{frame.output_index}\t{frame.source_index}\t{frame.timestamp_sec:.6f}\t{path}\t{sha256 or ''}\n")


def _jsonable_args(args: argparse.Namespace | dict | object) -> dict:
    if isinstance(args, dict):
        raw = args
    elif hasattr(args, "__dict__"):
        raw = vars(args)
    else:
        raw = {}
    return {key: _path_to_manifest(value) if isinstance(value, Path) else value for key, value in sorted(raw.items())}


def _path_to_manifest(path: Path) -> str:
    return path.as_posix()


def write_run_manifest(
    manifest_path: Path,
    *,
    video_path: Path,
    output_dir: Path,
    selected_frames_path: Path,
    report_path: Path,
    summary_path: Path,
    filtered_video_path: Path | None,
    src_fps: float,
    total_frames: int,
    selected_count: int,
    thresholds: QualityThresholds,
    args: argparse.Namespace | dict | object,
    analyzed_count: int | None = None,
) -> None:
    if analyzed_count is None:
        analyzed_count = total_frames
    stats = _selection_stats(
        total_frames=total_frames,
        analyzed_count=analyzed_count,
        selected_count=selected_count,
    )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "video": _path_to_manifest(video_path),
            "fps": src_fps,
            "frames": total_frames,
        },
        "outputs": {
            "frame_dir": _path_to_manifest(output_dir),
            "selected_frames": _path_to_manifest(selected_frames_path),
            "report": _path_to_manifest(report_path),
            "summary": _path_to_manifest(summary_path),
            "filtered_video": None if filtered_video_path is None else _path_to_manifest(filtered_video_path),
        },
        "selection": stats,
        "thresholds": {
            "min_sharpness": thresholds.min_sharpness,
            "min_brightness": thresholds.min_brightness,
            "max_brightness": thresholds.max_brightness,
            "min_contrast": thresholds.min_contrast,
        },
        "parameters": _jsonable_args(args),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
