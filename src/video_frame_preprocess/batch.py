#!/usr/bin/env python3
"""Batch runner for the isolated video preprocessing pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class BatchConfig:
    input_dir: Path
    output_dir: Path
    selection: str = "quality_filter"
    scan_fps: float = 0.0
    sharpness_quantile: float = 0.10
    max_drop_ratio: float = 0.08
    max_consecutive_drops: int = 2
    min_gap: int = 1
    image_ext: str = "jpg"
    jpg_quality: int = 95
    write_filtered_video: bool = True


@dataclass(frozen=True)
class BatchResult:
    video: str
    source_frames: int
    selected_frames: int
    dropped_frames: int
    retention_ratio: float
    output_dir: str
    filtered_video: str
    manifest: str
    success: bool
    error: str


def load_config(path: Path) -> BatchConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return BatchConfig(
        input_dir=Path(data["input_dir"]),
        output_dir=Path(data["output_dir"]),
        selection=data.get("selection", "quality_filter"),
        scan_fps=float(data.get("scan_fps", 0.0)),
        sharpness_quantile=float(data.get("sharpness_quantile", 0.10)),
        max_drop_ratio=float(data.get("max_drop_ratio", 0.08)),
        max_consecutive_drops=int(data.get("max_consecutive_drops", 2)),
        min_gap=int(data.get("min_gap", 1)),
        image_ext=data.get("image_ext", "jpg"),
        jpg_quality=int(data.get("jpg_quality", 95)),
        write_filtered_video=bool(data.get("write_filtered_video", True)),
    )


def write_batch_summary(path: Path, results: Sequence[BatchResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "video",
                "source_frames",
                "selected_frames",
                "dropped_frames",
                "retention_ratio",
                "output_dir",
                "filtered_video",
                "manifest",
                "success",
                "error",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "video": result.video,
                    "source_frames": result.source_frames,
                    "selected_frames": result.selected_frames,
                    "dropped_frames": result.dropped_frames,
                    "retention_ratio": f"{result.retention_ratio:.6f}",
                    "output_dir": result.output_dir,
                    "filtered_video": result.filtered_video,
                    "manifest": result.manifest,
                    "success": int(result.success),
                    "error": result.error,
                }
            )


def _discover_videos(input_dir: Path, names: Sequence[str] | None) -> list[Path]:
    if names:
        return [input_dir / name for name in names]
    return sorted(input_dir.glob("*.mp4"))


def _result_from_manifest(video: Path, manifest_path: Path, success: bool, error: str = "") -> BatchResult:
    if not success:
        return BatchResult(
            video=video.name,
            source_frames=0,
            selected_frames=0,
            dropped_frames=0,
            retention_ratio=0.0,
            output_dir="",
            filtered_video="",
            manifest=manifest_path.as_posix(),
            success=False,
            error=error,
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selection = manifest["selection"]
    outputs = manifest["outputs"]
    return BatchResult(
        video=video.name,
        source_frames=int(manifest["source"]["frames"]),
        selected_frames=int(selection["selected_frames"]),
        dropped_frames=int(selection["dropped_frames"]),
        retention_ratio=float(selection["retention_ratio"]),
        output_dir=outputs["frame_dir"],
        filtered_video=outputs["filtered_video"] or "",
        manifest=manifest_path.as_posix(),
        success=True,
        error="",
    )


def run_one(video: Path, config: BatchConfig, *, dry_run: bool = False) -> BatchResult:
    stem = video.stem
    frame_dir = config.output_dir / f"{stem}_clear_frames"
    filtered_video = config.output_dir / f"{stem}_filtered_clean.mp4"
    manifest = frame_dir / "run_manifest.json"
    cmd = [
        sys.executable,
        "-m",
        "video_frame_preprocess.quality_filter",
        "--video",
        str(video),
        "--output",
        str(frame_dir),
        "--selection",
        config.selection,
        "--scan_fps",
        str(config.scan_fps),
        "--sharpness_quantile",
        str(config.sharpness_quantile),
        "--max_drop_ratio",
        str(config.max_drop_ratio),
        "--max_consecutive_drops",
        str(config.max_consecutive_drops),
        "--min_gap",
        str(config.min_gap),
        "--image_ext",
        config.image_ext,
        "--jpg_quality",
        str(config.jpg_quality),
        "--clean",
    ]
    if config.write_filtered_video and not dry_run:
        cmd.extend(["--filtered_video", str(filtered_video)])
    if dry_run:
        cmd.append("--dry_run")

    env = os.environ.copy()
    src_dir = Path(__file__).resolve().parents[1]
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(src_dir) if not existing_pythonpath else str(src_dir) + os.pathsep + existing_pythonpath

    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True, env=env)
        return _result_from_manifest(video, manifest, success=True)
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or exc.stdout or str(exc)).strip()
        return _result_from_manifest(video, manifest, success=False, error=error)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch preprocess pipeline videos.")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config" / "default.json")
    parser.add_argument("--videos", nargs="*", default=None, help="Optional video filenames under input_dir")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    videos = _discover_videos(config.input_dir, args.videos)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for video in videos:
        if not video.is_file():
            results.append(_result_from_manifest(video, config.output_dir / video.stem / "run_manifest.json", False, "video not found"))
            continue
        result = run_one(video, config, dry_run=args.dry_run)
        results.append(result)
        status = "OK" if result.success else "FAIL"
        print(f"{status}: {video.name} selected={result.selected_frames}/{result.source_frames}")

    summary_path = config.output_dir / "batch_summary.csv"
    write_batch_summary(summary_path, results)
    print(f"Batch summary: {summary_path}")
    return 1 if any(not result.success for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
