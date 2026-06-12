#!/usr/bin/env python3
"""Select clean and useful frames from shaky or blurry videos."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

from .models import FrameCandidate, QualityMetrics, QualityThresholds, SelectedFrame
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
    "choose_best_frame_candidates",
    "choose_frame_candidates",
    "choose_quality_filter_candidates",
    "choose_quality_filter_candidates_safe",
    "choose_timeline_frame_indices",
    "clean_output_dir",
    "derive_thresholds",
    "iter_video_candidates",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select clear frames from a shaky/blurry video for LingBot-Map preprocessing."
    )
    parser.add_argument("--video", required=True, type=Path, help="Input video path, e.g. data/user-video/test1.mp4")
    parser.add_argument("--output", required=True, type=Path, help="Output image folder")
    parser.add_argument("--target_fps", type=float, default=5.0, help="Maximum output FPS after quality filtering")
    parser.add_argument(
        "--scan_fps",
        type=float,
        default=0.0,
        help="FPS to inspect before filtering. 0 means inspect every source frame.",
    )
    parser.add_argument("--min_gap", type=int, default=1, help="Minimum source-frame gap between selected frames")
    parser.add_argument(
        "--max_drop_ratio",
        type=float,
        default=0.08,
        help="Maximum fraction of frames to drop in quality_filter mode",
    )
    parser.add_argument(
        "--max_consecutive_drops",
        type=int,
        default=2,
        help="Maximum consecutive dropped source frames in quality_filter mode",
    )
    parser.add_argument(
        "--selection",
        choices=["quality_filter", "local_best", "first_pass"],
        default="quality_filter",
        help=(
            "quality_filter keeps most frames and only drops bad-quality frames; "
            "local_best picks one frame per target-FPS bucket; first_pass keeps first qualifying frames."
        ),
    )
    parser.add_argument(
        "--strict_quality",
        action="store_true",
        help="Do not fill empty time buckets with the best available frame. This may create timeline jumps.",
    )
    parser.add_argument(
        "--min_sharpness",
        type=float,
        default=None,
        help="Absolute Laplacian-variance threshold. If omitted, use --sharpness_quantile.",
    )
    parser.add_argument(
        "--sharpness_quantile",
        type=float,
        default=0.10,
        help="Video-relative sharpness cutoff when --min_sharpness is omitted",
    )
    parser.add_argument("--min_brightness", type=float, default=20.0)
    parser.add_argument("--max_brightness", type=float, default=245.0)
    parser.add_argument("--min_contrast", type=float, default=8.0)
    parser.add_argument("--resize_width", type=int, default=512, help="Width used for quality analysis")
    parser.add_argument("--image_ext", default="png", choices=["png", "jpg", "jpeg"])
    parser.add_argument("--jpg_quality", type=int, default=95)
    parser.add_argument("--report", type=Path, default=None, help="CSV report path. Default: <output>/frame_report.csv")
    parser.add_argument("--summary", type=Path, default=None, help="JSON summary path. Default: <output>/summary.json")
    parser.add_argument(
        "--selected_frames",
        type=Path,
        default=None,
        help="TSV selected-frame list. Default: <output>/selected_frames.txt",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Run manifest path. Default: <output>/run_manifest.json")
    parser.add_argument("--preview_video", type=Path, default=None, help="Optional MP4 preview path")
    parser.add_argument("--preview_fps", type=float, default=10.0)
    parser.add_argument("--preview_width", type=int, default=960)
    parser.add_argument(
        "--preview_mode",
        choices=["timeline", "compressed"],
        default="timeline",
        help="timeline preserves source duration; compressed plays selected frames back-to-back.",
    )
    parser.add_argument(
        "--audit_video",
        type=Path,
        default=None,
        help="Optional MP4 that preserves original video frames and overlays KEEP/DROP quality decisions.",
    )
    parser.add_argument("--audit_width", type=int, default=960)
    parser.add_argument(
        "--filtered_video",
        type=Path,
        default=None,
        help="Optional clean MP4 made only from selected frames. No text or metrics are drawn.",
    )
    parser.add_argument("--filtered_video_fps", type=float, default=0.0, help="0 uses source FPS")
    parser.add_argument("--filtered_video_width", type=int, default=0, help="0 keeps selected frame width")
    parser.add_argument("--max_frames", type=int, default=None, help="Analyze at most this many sampled frames")
    parser.add_argument("--clean", action="store_true", help="Remove previous frame outputs in --output before saving")
    parser.add_argument("--dry_run", action="store_true", help="Analyze and report without saving selected images")
    return parser


def _choose_candidates(
    args: argparse.Namespace,
    candidates: Sequence[FrameCandidate],
    thresholds: QualityThresholds,
) -> list[FrameCandidate]:
    if args.selection == "quality_filter":
        return choose_quality_filter_candidates_safe(
            candidates,
            thresholds=thresholds,
            min_gap=args.min_gap,
            max_drop_ratio=args.max_drop_ratio,
            max_consecutive_drops=args.max_consecutive_drops,
        )
    if args.selection == "local_best":
        return choose_best_frame_candidates(
            candidates,
            thresholds=thresholds,
            target_fps=args.target_fps,
            min_gap=args.min_gap,
            fill_missing_buckets=not args.strict_quality,
        )
    return choose_frame_candidates(candidates, thresholds=thresholds, min_gap=args.min_gap)


def _dry_run_selected(chosen: Sequence[FrameCandidate]) -> list[SelectedFrame]:
    return [
        SelectedFrame(
            source_index=c.index,
            output_index=i,
            timestamp_sec=c.timestamp_sec,
            quality=c.quality,
            output_path=None,
        )
        for i, c in enumerate(chosen)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    video_path = args.video
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    candidates, src_fps, total_frames = iter_video_candidates(
        video_path,
        scan_fps=args.scan_fps,
        resize_width=args.resize_width,
        max_frames=args.max_frames,
    )
    if not candidates:
        raise RuntimeError(f"No frames could be analyzed from video: {video_path}")

    thresholds = derive_thresholds(
        candidates,
        min_sharpness=args.min_sharpness,
        sharpness_quantile=args.sharpness_quantile,
        min_brightness=args.min_brightness,
        max_brightness=args.max_brightness,
        min_contrast=args.min_contrast,
    )
    chosen = _choose_candidates(args, candidates, thresholds)

    output_dir = args.output
    if args.dry_run:
        selected = _dry_run_selected(chosen)
    else:
        if args.clean:
            clean_output_dir(output_dir, args.image_ext)
        selected = save_selected_frames(
            video_path,
            chosen,
            output_dir,
            image_ext=args.image_ext,
            jpg_quality=args.jpg_quality,
        )

    report_path = args.report or (output_dir / "frame_report.csv")
    write_report(report_path, candidates, selected, thresholds)
    summary_path = args.summary or (output_dir / "summary.json")
    write_summary_json(
        summary_path,
        video_path=video_path,
        src_fps=src_fps,
        total_frames=total_frames,
        candidates=candidates,
        selected=selected,
        thresholds=thresholds,
        target_fps=args.target_fps,
        scan_fps=args.scan_fps,
    )
    selected_frames_path = args.selected_frames or (output_dir / "selected_frames.txt")
    write_selected_frames_txt(selected_frames_path, selected)

    preview_skipped = False
    source_duration_sec = total_frames / src_fps if src_fps > 0 and total_frames > 0 else 0.0
    if args.preview_video is not None and not args.dry_run:
        frame_paths = [frame.output_path for frame in selected if frame.output_path is not None]
        if frame_paths:
            if args.preview_mode == "timeline":
                write_timeline_preview_video(
                    selected,
                    args.preview_video,
                    fps=args.preview_fps,
                    width=args.preview_width,
                    source_duration_sec=source_duration_sec,
                )
            else:
                write_preview_video(frame_paths, args.preview_video, fps=args.preview_fps, width=args.preview_width)
        else:
            preview_skipped = True

    print(f"Video: {video_path}")
    print(f"Source: {total_frames} frames @ {src_fps:.3f} FPS")
    print(f"Analyzed candidates: {len(candidates)}")
    print(f"Selected frames: {len(selected)}")
    print(
        f"Selection: {args.selection}, target_fps={args.target_fps}, "
        f"scan_fps={args.scan_fps}, fill_gaps={not args.strict_quality}, "
        f"max_drop_ratio={args.max_drop_ratio}, max_consecutive_drops={args.max_consecutive_drops}"
    )
    print(
        "Thresholds: "
        f"sharpness>={thresholds.min_sharpness:.2f}, "
        f"brightness={thresholds.min_brightness:.1f}-{thresholds.max_brightness:.1f}, "
        f"contrast>={thresholds.min_contrast:.1f}"
    )
    if not args.dry_run:
        print(f"Output images: {output_dir}")
    if args.preview_video is not None and not args.dry_run and not preview_skipped:
        print(f"Preview video: {args.preview_video} ({args.preview_mode})")
    elif preview_skipped:
        print("Preview video skipped: no selected frames")
    if args.audit_video is not None and not args.dry_run:
        write_audit_video(
            video_path,
            args.audit_video,
            candidates=candidates,
            selected=selected,
            thresholds=thresholds,
            width=args.audit_width,
        )
        print(f"Audit video: {args.audit_video}")
    if args.filtered_video is not None and not args.dry_run:
        filtered_fps = args.filtered_video_fps if args.filtered_video_fps > 0 else src_fps
        write_filtered_video(
            selected,
            args.filtered_video,
            fps=filtered_fps,
            width=args.filtered_video_width,
        )
        print(f"Filtered clean video: {args.filtered_video}")

    manifest_path = args.manifest or (output_dir / "run_manifest.json")
    manifest_args = SimpleNamespace(**vars(args))
    write_run_manifest(
        manifest_path,
        video_path=video_path,
        output_dir=output_dir,
        selected_frames_path=selected_frames_path,
        report_path=report_path,
        summary_path=summary_path,
        filtered_video_path=args.filtered_video,
        src_fps=src_fps,
        total_frames=total_frames,
        selected_count=len(selected),
        thresholds=thresholds,
        args=manifest_args,
        analyzed_count=len(candidates),
    )
    print(f"Selected frames: {selected_frames_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
