#!/usr/bin/env python3
"""Backward-compatible imports for the video frame preprocessing CLI."""

from __future__ import annotations

from .models import FrameCandidate, QualityMetrics, QualityThresholds, SelectedFrame
from .pipeline import build_parser, main
from .quality import analyze_frame_quality, derive_thresholds, passes_quality, quality_score
from .reporting import write_report, write_run_manifest, write_selected_frames_txt, write_summary_json
from .selection import (
    choose_best_frame_candidates,
    choose_frame_candidates,
    choose_quality_filter_candidates,
    choose_quality_filter_candidates_safe,
)
from .video_io import (
    choose_timeline_frame_indices,
    clean_output_dir,
    iter_video_candidates,
    save_selected_frames,
    timeline_preview_duration,
    write_audit_video,
    write_filtered_video,
    write_preview_video,
    write_timeline_preview_video,
)

__all__ = [
    "FrameCandidate",
    "QualityMetrics",
    "QualityThresholds",
    "SelectedFrame",
    "analyze_frame_quality",
    "build_parser",
    "choose_best_frame_candidates",
    "choose_frame_candidates",
    "choose_quality_filter_candidates",
    "choose_quality_filter_candidates_safe",
    "choose_timeline_frame_indices",
    "clean_output_dir",
    "derive_thresholds",
    "iter_video_candidates",
    "main",
    "passes_quality",
    "quality_score",
    "save_selected_frames",
    "timeline_preview_duration",
    "write_audit_video",
    "write_filtered_video",
    "write_preview_video",
    "write_report",
    "write_run_manifest",
    "write_selected_frames_txt",
    "write_summary_json",
    "write_timeline_preview_video",
]


if __name__ == "__main__":
    raise SystemExit(main())
