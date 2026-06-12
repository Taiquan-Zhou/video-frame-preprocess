"""Video decoding, frame writing, and preview encoding."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np

from .models import FrameCandidate, QualityThresholds, SelectedFrame
from .quality import analyze_frame_quality


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_video_candidates(
    video_path: Path,
    *,
    scan_fps: float,
    resize_width: int,
    max_frames: int | None = None,
) -> tuple[list[FrameCandidate], float, int]:
    """Read a video and return sampled frame candidates plus source metadata."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_interval = max(1, round(src_fps / scan_fps)) if scan_fps > 0 else 1

    candidates: list[FrameCandidate] = []
    frame_index = 0
    try:
        while True:
            if frame_index % sample_interval == 0:
                ok, frame = cap.read()
                if not ok:
                    break
                timestamp_sec = frame_index / src_fps if src_fps > 0 else 0.0
                candidates.append(
                    FrameCandidate(
                        index=frame_index,
                        timestamp_sec=timestamp_sec,
                        quality=analyze_frame_quality(frame, resize_width=resize_width),
                    )
                )
                if max_frames is not None and len(candidates) >= max_frames:
                    break
            elif not cap.grab():
                break
            frame_index += 1
    finally:
        cap.release()

    return candidates, src_fps, total_frames


def clean_output_dir(output_dir: Path, image_ext: str) -> None:
    """Remove this tool's previous frame/report outputs from the target folder."""
    del image_ext
    if not output_dir.exists():
        return
    for path in output_dir.glob("frame_*_src_*.*"):
        path.unlink()
    for name in ("frame_report.csv", "summary.json", "selected_frames.txt", "run_manifest.json"):
        path = output_dir / name
        if path.exists():
            path.unlink()


def save_selected_frames(
    video_path: Path,
    selected: Sequence[FrameCandidate],
    output_dir: Path,
    *,
    image_ext: str,
    jpg_quality: int,
) -> list[SelectedFrame]:
    """Decode selected source frames and save them as images."""
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_by_index = {candidate.index: candidate for candidate in selected}
    if not selected_by_index:
        return []

    ext = image_ext.strip().lower().lstrip(".") or "png"
    if ext not in {"png", "jpg", "jpeg"}:
        raise ValueError("--image_ext must be one of: png, jpg, jpeg")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    saved: list[SelectedFrame] = []
    frame_index = 0
    output_index = 0
    encode_params = []
    if ext in {"jpg", "jpeg"}:
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, min(max(int(jpg_quality), 1), 100)]

    try:
        while len(saved) < len(selected_by_index):
            ok, frame = cap.read()
            if not ok:
                break
            candidate = selected_by_index.get(frame_index)
            if candidate is not None:
                output_path = output_dir / f"frame_{output_index:06d}_src_{frame_index:06d}.{ext}"
                if not cv2.imwrite(str(output_path), frame, encode_params):
                    raise RuntimeError(f"Failed to write frame: {output_path}")
                saved.append(
                    SelectedFrame(
                        source_index=frame_index,
                        output_index=output_index,
                        timestamp_sec=candidate.timestamp_sec,
                        quality=candidate.quality,
                        output_path=output_path,
                        sha256=file_sha256(output_path),
                    )
                )
                output_index += 1
            frame_index += 1
    finally:
        cap.release()

    return saved


def write_preview_video(frame_paths: Sequence[Path], output_path: Path, *, fps: float, width: int) -> None:
    """Encode selected image frames into an MP4 preview using OpenCV."""
    if not frame_paths:
        raise ValueError("Cannot create preview video without frames")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    first = cv2.imread(str(frame_paths[0]))
    if first is None:
        raise ValueError(f"Cannot read preview frame: {frame_paths[0]}")
    if width > 0 and first.shape[1] != width:
        scale = width / first.shape[1]
        height = max(1, round(first.shape[0] * scale))
        size = (width, height)
    else:
        size = (first.shape[1], first.shape[0])

    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)  # type: ignore[attr-defined]
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create preview video: {output_path}")

    try:
        for frame_path in frame_paths:
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise ValueError(f"Cannot read preview frame: {frame_path}")
            if (frame.shape[1], frame.shape[0]) != size:
                frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            writer.write(frame)
    finally:
        writer.release()


def timeline_preview_duration(frame_count: int, fps: float) -> float:
    if fps <= 0:
        raise ValueError("fps must be positive")
    return frame_count / fps


def choose_timeline_frame_indices(
    selected: Sequence[SelectedFrame],
    *,
    preview_fps: float,
    source_duration_sec: float,
) -> list[int]:
    """Map each preview timestamp to the nearest selected frame index."""
    if not selected:
        return []
    if preview_fps <= 0:
        raise ValueError("preview_fps must be positive")
    if source_duration_sec <= 0:
        source_duration_sec = selected[-1].timestamp_sec

    preview_count = max(1, int(round(source_duration_sec * preview_fps)))
    selected_times = np.array([frame.timestamp_sec for frame in selected], dtype=np.float64)
    indices: list[int] = []
    cursor = 0
    for i in range(preview_count):
        timestamp = i / preview_fps
        while cursor + 1 < len(selected_times) and selected_times[cursor + 1] <= timestamp:
            cursor += 1
        if cursor + 1 < len(selected_times):
            prev_delta = abs(timestamp - selected_times[cursor])
            next_delta = abs(selected_times[cursor + 1] - timestamp)
            indices.append(cursor + 1 if next_delta < prev_delta else cursor)
        else:
            indices.append(cursor)
    return indices


def write_timeline_preview_video(
    selected: Sequence[SelectedFrame],
    output_path: Path,
    *,
    fps: float,
    width: int,
    source_duration_sec: float,
) -> None:
    """Encode a preview that preserves the source video's timeline."""
    if not selected:
        raise ValueError("Cannot create preview video without selected frames")
    frame_indices = choose_timeline_frame_indices(
        selected,
        preview_fps=fps,
        source_duration_sec=source_duration_sec,
    )
    frame_paths = [selected[index].output_path for index in frame_indices]
    if any(path is None for path in frame_paths):
        raise ValueError("Selected frames must have output_path for preview generation")
    write_preview_video([path for path in frame_paths if path is not None], output_path, fps=fps, width=width)


def write_filtered_video(
    selected: Sequence[SelectedFrame],
    output_path: Path,
    *,
    fps: float,
    width: int,
) -> None:
    """Encode selected clean frames into a video without overlays."""
    if not selected:
        raise ValueError("Cannot create filtered video without selected frames")
    frame_paths = [frame.output_path for frame in selected]
    if any(path is None for path in frame_paths):
        raise ValueError("Selected frames must have output_path for filtered video generation")
    write_preview_video([path for path in frame_paths if path is not None], output_path, fps=fps, width=width)


def _resize_for_video(frame: np.ndarray, width: int) -> np.ndarray:
    if width > 0 and frame.shape[1] != width:
        scale = width / frame.shape[1]
        height = max(1, round(frame.shape[0] * scale))
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    return frame


def _draw_audit_overlay(
    frame: np.ndarray,
    *,
    frame_index: int,
    candidate: FrameCandidate | None,
    is_selected: bool,
    thresholds: QualityThresholds,
) -> np.ndarray:
    out = frame.copy()
    status = "KEEP" if is_selected else "DROP"
    color = (60, 220, 60) if is_selected else (40, 80, 255)
    cv2.rectangle(out, (0, 0), (out.shape[1], 88), (0, 0, 0), thickness=-1)
    cv2.putText(out, f"{status}  frame={frame_index}", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    if candidate is not None:
        q = candidate.quality
        cv2.putText(
            out,
            f"sharp={q.sharpness:.0f}/{thresholds.min_sharpness:.0f}  "
            f"bright={q.brightness:.1f}  contrast={q.contrast:.1f}",
            (18, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (230, 230, 230),
            2,
        )
    else:
        cv2.putText(out, "not analyzed", (18, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (230, 230, 230), 2)
    return out


def write_audit_video(
    video_path: Path,
    output_path: Path,
    *,
    candidates: Sequence[FrameCandidate],
    selected: Sequence[SelectedFrame],
    thresholds: QualityThresholds,
    width: int,
) -> None:
    """Create a video with original frame timing and quality-selection overlays."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    candidate_by_index = {candidate.index: candidate for candidate in candidates}
    selected_indices = {frame.source_index for frame in selected}

    ok, first = cap.read()
    if not ok:
        cap.release()
        raise ValueError(f"Cannot read first frame from video: {video_path}")

    first = _resize_for_video(first, width)
    size = (first.shape[1], first.shape[0])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)  # type: ignore[attr-defined]
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot create audit video: {output_path}")

    try:
        frame_index = 0
        frame = first
        while True:
            candidate = candidate_by_index.get(frame_index)
            writer.write(
                _draw_audit_overlay(
                    frame,
                    frame_index=frame_index,
                    candidate=candidate,
                    is_selected=frame_index in selected_indices,
                    thresholds=thresholds,
                )
            )
            frame_index += 1
            ok, frame = cap.read()
            if not ok:
                break
            frame = _resize_for_video(frame, width)
    finally:
        writer.release()
        cap.release()
