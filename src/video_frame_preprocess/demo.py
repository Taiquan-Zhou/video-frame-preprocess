#!/usr/bin/env python3
"""Generate deterministic demo videos for smoke tests and examples."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np


def create_demo_video(
    output_path: Path,
    *,
    frame_count: int = 24,
    fps: float = 6.0,
    size: tuple[int, int] = (160, 96),
) -> None:
    """Write a small deterministic MP4 with varying motion and brightness."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))  # type: ignore[attr-defined]
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create demo video: {output_path}")

    try:
        for i in range(frame_count):
            base = 35 + (i * 7) % 120
            frame = np.full((height, width, 3), base, dtype=np.uint8)
            x = 10 + (i * 5) % max(1, width - 40)
            y = height // 2
            cv2.rectangle(frame, (x, y - 12), (x + 30, y + 12), (230, 230, 230), -1)
            cv2.putText(frame, f"{i:02d}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            writer.write(frame)
    finally:
        writer.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a deterministic demo video for video-frame-preprocess.")
    parser.add_argument("--output", type=Path, default=Path("input/demo.mp4"))
    parser.add_argument("--frame_count", type=int, default=24)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=96)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    create_demo_video(
        args.output,
        frame_count=args.frame_count,
        fps=args.fps,
        size=(args.width, args.height),
    )
    print(f"Demo video: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
