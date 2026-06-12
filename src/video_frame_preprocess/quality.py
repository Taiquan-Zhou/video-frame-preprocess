"""Frame quality metrics and thresholding."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from .models import FrameCandidate, QualityMetrics, QualityThresholds


def analyze_frame_quality(frame_bgr: np.ndarray, resize_width: int = 512) -> QualityMetrics:
    """Compute cheap quality metrics for a BGR frame."""
    if frame_bgr is None or frame_bgr.size == 0:
        raise ValueError("frame_bgr must be a non-empty image")

    if resize_width > 0 and frame_bgr.shape[1] > resize_width:
        scale = resize_width / frame_bgr.shape[1]
        resized_h = max(1, round(frame_bgr.shape[0] * scale))
        frame_bgr = cv2.resize(frame_bgr, (resize_width, resized_h), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return QualityMetrics(
        sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        brightness=float(gray.mean()),
        contrast=float(gray.std()),
    )


def derive_thresholds(
    candidates: Sequence[FrameCandidate],
    *,
    min_sharpness: float | None,
    sharpness_quantile: float,
    min_brightness: float,
    max_brightness: float,
    min_contrast: float,
) -> QualityThresholds:
    """Create thresholds, deriving sharpness from the video distribution by default."""
    if not candidates:
        raise ValueError("Cannot derive thresholds from an empty candidate list")
    if min_sharpness is None:
        sharpness_values = np.array([c.quality.sharpness for c in candidates], dtype=np.float64)
        quantile = min(max(float(sharpness_quantile), 0.0), 1.0)
        min_sharpness = float(np.quantile(sharpness_values, quantile))

    return QualityThresholds(
        min_sharpness=float(min_sharpness),
        min_brightness=float(min_brightness),
        max_brightness=float(max_brightness),
        min_contrast=float(min_contrast),
    )


def passes_quality(candidate: FrameCandidate, thresholds: QualityThresholds) -> bool:
    quality = candidate.quality
    return (
        quality.sharpness >= thresholds.min_sharpness
        and thresholds.min_brightness <= quality.brightness <= thresholds.max_brightness
        and quality.contrast >= thresholds.min_contrast
    )


def quality_score(candidate: FrameCandidate, thresholds: QualityThresholds) -> float:
    """Rank a candidate among frames that already passed hard thresholds."""
    quality = candidate.quality
    min_sharpness = max(thresholds.min_sharpness, 1e-6)
    min_contrast = max(thresholds.min_contrast, 1e-6)
    sharpness_score = min(quality.sharpness / min_sharpness, 20.0)
    contrast_score = min(quality.contrast / min_contrast, 3.0)

    brightness_mid = (thresholds.min_brightness + thresholds.max_brightness) / 2.0
    brightness_half_range = max((thresholds.max_brightness - thresholds.min_brightness) / 2.0, 1e-6)
    brightness_score = 1.0 - abs(quality.brightness - brightness_mid) / brightness_half_range
    brightness_score = min(max(brightness_score, 0.0), 1.0)

    return sharpness_score * 0.70 + contrast_score * 0.20 + brightness_score * 0.10
