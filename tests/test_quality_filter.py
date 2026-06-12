import json
import unittest
from pathlib import Path

import cv2
import numpy as np

from video_frame_preprocess.quality_filter import (
    FrameCandidate,
    QualityMetrics,
    QualityThresholds,
    SelectedFrame,
    analyze_frame_quality,
    choose_best_frame_candidates,
    choose_frame_candidates,
    choose_quality_filter_candidates,
    choose_quality_filter_candidates_safe,
    choose_timeline_frame_indices,
    timeline_preview_duration,
    write_audit_video,
    write_filtered_video,
    write_preview_video,
    write_run_manifest,
    write_selected_frames_txt,
    write_summary_json,
    write_timeline_preview_video,
)


def _checkerboard(size=128, block=8):
    y, x = np.indices((size, size))
    pattern = ((x // block + y // block) % 2 * 255).astype(np.uint8)
    return cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGR)


class SelectClearFramesTest(unittest.TestCase):
    def test_sharpness_score_is_higher_for_sharp_frame_than_blurred_frame(self):
        sharp = _checkerboard()
        blurred = cv2.GaussianBlur(sharp, (21, 21), 0)

        sharp_quality = analyze_frame_quality(sharp, resize_width=128)
        blurred_quality = analyze_frame_quality(blurred, resize_width=128)

        self.assertGreater(sharp_quality.sharpness, blurred_quality.sharpness * 5)
        self.assertGreater(sharp_quality.contrast, blurred_quality.contrast)

    def test_choose_frame_candidates_filters_blurry_frames_and_enforces_gap(self):
        candidates = [
            FrameCandidate(index=0, timestamp_sec=0.0, quality=analyze_frame_quality(_checkerboard())),
            FrameCandidate(
                index=1,
                timestamp_sec=0.1,
                quality=analyze_frame_quality(cv2.GaussianBlur(_checkerboard(), (21, 21), 0)),
            ),
            FrameCandidate(index=2, timestamp_sec=0.2, quality=analyze_frame_quality(_checkerboard())),
            FrameCandidate(index=4, timestamp_sec=0.4, quality=analyze_frame_quality(_checkerboard())),
        ]
        thresholds = QualityThresholds(
            min_sharpness=1000.0,
            min_brightness=1.0,
            max_brightness=254.0,
            min_contrast=10.0,
        )

        selected = choose_frame_candidates(candidates, thresholds=thresholds, min_gap=3)

        self.assertEqual([candidate.index for candidate in selected], [0, 4])

    def test_choose_best_frame_candidates_uses_highest_quality_in_each_time_bucket(self):
        candidates = [
            FrameCandidate(index=0, timestamp_sec=0.00, quality=QualityMetrics(100.0, 40.0, 20.0)),
            FrameCandidate(index=3, timestamp_sec=0.30, quality=QualityMetrics(200.0, 120.0, 30.0)),
            FrameCandidate(index=4, timestamp_sec=0.40, quality=QualityMetrics(800.0, 120.0, 30.0)),
            FrameCandidate(index=10, timestamp_sec=1.00, quality=QualityMetrics(300.0, 120.0, 30.0)),
        ]
        thresholds = QualityThresholds(
            min_sharpness=100.0,
            min_brightness=1.0,
            max_brightness=254.0,
            min_contrast=1.0,
        )

        selected = choose_best_frame_candidates(
            candidates,
            thresholds=thresholds,
            target_fps=1.0,
            min_gap=1,
        )

        self.assertEqual([candidate.index for candidate in selected], [4, 10])

    def test_choose_best_frame_candidates_can_fill_empty_buckets_for_continuity(self):
        candidates = [
            FrameCandidate(index=0, timestamp_sec=0.00, quality=QualityMetrics(100.0, 120.0, 30.0)),
            FrameCandidate(index=5, timestamp_sec=0.50, quality=QualityMetrics(200.0, 120.0, 30.0)),
            FrameCandidate(index=10, timestamp_sec=1.00, quality=QualityMetrics(900.0, 120.0, 30.0)),
        ]
        thresholds = QualityThresholds(
            min_sharpness=500.0,
            min_brightness=1.0,
            max_brightness=254.0,
            min_contrast=1.0,
        )

        strict = choose_best_frame_candidates(
            candidates,
            thresholds=thresholds,
            target_fps=2.0,
            min_gap=1,
            fill_missing_buckets=False,
        )
        filled = choose_best_frame_candidates(
            candidates,
            thresholds=thresholds,
            target_fps=2.0,
            min_gap=1,
            fill_missing_buckets=True,
        )

        self.assertEqual([candidate.index for candidate in strict], [10])
        self.assertEqual([candidate.index for candidate in filled], [0, 5, 10])

    def test_choose_quality_filter_candidates_keeps_most_frames_and_only_drops_bad_quality(self):
        candidates = [
            FrameCandidate(index=i, timestamp_sec=i / 10.0, quality=QualityMetrics(1000.0, 120.0, 35.0))
            for i in range(20)
        ]
        candidates[3] = FrameCandidate(index=3, timestamp_sec=0.3, quality=QualityMetrics(20.0, 120.0, 35.0))
        candidates[14] = FrameCandidate(index=14, timestamp_sec=1.4, quality=QualityMetrics(40.0, 120.0, 35.0))
        thresholds = QualityThresholds(
            min_sharpness=100.0,
            min_brightness=20.0,
            max_brightness=245.0,
            min_contrast=8.0,
        )

        selected = choose_quality_filter_candidates(candidates, thresholds=thresholds, min_gap=1)

        self.assertEqual(len(selected), 18)
        self.assertNotIn(3, [candidate.index for candidate in selected])
        self.assertNotIn(14, [candidate.index for candidate in selected])

    def test_safe_quality_filter_caps_total_drops_by_restoring_best_rejected_frames(self):
        candidates = [
            FrameCandidate(index=i, timestamp_sec=i / 10.0, quality=QualityMetrics(1000.0, 120.0, 35.0))
            for i in range(20)
        ]
        for i in range(10):
            candidates[i] = FrameCandidate(index=i, timestamp_sec=i / 10.0, quality=QualityMetrics(10.0 + i, 120.0, 35.0))
        thresholds = QualityThresholds(
            min_sharpness=100.0,
            min_brightness=20.0,
            max_brightness=245.0,
            min_contrast=8.0,
        )

        selected = choose_quality_filter_candidates_safe(
            candidates,
            thresholds=thresholds,
            min_gap=1,
            max_drop_ratio=0.10,
            max_consecutive_drops=3,
        )

        self.assertGreaterEqual(len(selected), 18)
        self.assertLessEqual(len(candidates) - len(selected), 2)

    def test_safe_quality_filter_limits_consecutive_drops(self):
        candidates = [
            FrameCandidate(index=i, timestamp_sec=i / 10.0, quality=QualityMetrics(1000.0, 120.0, 35.0))
            for i in range(12)
        ]
        for i in range(2, 8):
            candidates[i] = FrameCandidate(index=i, timestamp_sec=i / 10.0, quality=QualityMetrics(10.0, 120.0, 35.0))
        thresholds = QualityThresholds(
            min_sharpness=100.0,
            min_brightness=20.0,
            max_brightness=245.0,
            min_contrast=8.0,
        )

        selected = choose_quality_filter_candidates_safe(
            candidates,
            thresholds=thresholds,
            min_gap=1,
            max_drop_ratio=0.50,
            max_consecutive_drops=2,
        )
        selected_indices = {candidate.index for candidate in selected}
        max_run = 0
        current = 0
        for candidate in candidates:
            if candidate.index in selected_indices:
                current = 0
            else:
                current += 1
                max_run = max(max_run, current)

        self.assertLessEqual(max_run, 2)

    def test_timeline_preview_indices_preserve_original_duration(self):
        selected = [
            SelectedFrame(0, 0, 0.0, QualityMetrics(1.0, 100.0, 20.0), None),
            SelectedFrame(10, 1, 1.0, QualityMetrics(1.0, 100.0, 20.0), None),
        ]

        indices = choose_timeline_frame_indices(selected, preview_fps=4.0, source_duration_sec=1.25)

        self.assertEqual(len(indices), 5)
        self.assertEqual(indices[0], 0)
        self.assertEqual(indices[-1], 1)
        self.assertAlmostEqual(timeline_preview_duration(5, 4.0), 1.25)

    def test_write_preview_video_creates_readable_mp4(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame_paths = []
            for i in range(3):
                image = np.full((64, 96, 3), i * 60, dtype=np.uint8)
                frame_path = tmp_path / f"frame_{i:06d}.png"
                self.assertTrue(cv2.imwrite(str(frame_path), image))
                frame_paths.append(frame_path)

            preview_path = tmp_path / "preview.mp4"
            write_preview_video(frame_paths, preview_path, fps=2.0, width=96)

            cap = cv2.VideoCapture(str(preview_path))
            try:
                self.assertTrue(cap.isOpened())
                self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 3)
            finally:
                cap.release()

    def test_write_timeline_preview_video_duplicates_frames_to_match_duration(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame_paths = []
            for i in range(2):
                image = np.full((64, 96, 3), i * 120, dtype=np.uint8)
                frame_path = tmp_path / f"frame_{i:06d}.png"
                self.assertTrue(cv2.imwrite(str(frame_path), image))
                frame_paths.append(frame_path)

            selected = [
                SelectedFrame(0, 0, 0.0, QualityMetrics(1.0, 100.0, 20.0), frame_paths[0]),
                SelectedFrame(10, 1, 1.0, QualityMetrics(1.0, 100.0, 20.0), frame_paths[1]),
            ]
            preview_path = tmp_path / "timeline.mp4"
            write_timeline_preview_video(
                selected,
                preview_path,
                fps=4.0,
                width=96,
                source_duration_sec=1.25,
            )

            cap = cv2.VideoCapture(str(preview_path))
            try:
                self.assertTrue(cap.isOpened())
                self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 5)
            finally:
                cap.release()

    def test_write_audit_video_keeps_original_frame_count(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.mp4"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (96, 64))
            self.assertTrue(writer.isOpened())
            try:
                for i in range(4):
                    writer.write(np.full((64, 96, 3), i * 40, dtype=np.uint8))
            finally:
                writer.release()

            candidates = [
                FrameCandidate(i, i / 5.0, QualityMetrics(100.0 + i, 120.0, 30.0))
                for i in range(4)
            ]
            selected = [
                SelectedFrame(1, 0, 0.2, candidates[1].quality, None),
                SelectedFrame(3, 1, 0.6, candidates[3].quality, None),
            ]
            audit = tmp_path / "audit.mp4"
            write_audit_video(
                source,
                audit,
                candidates=candidates,
                selected=selected,
                thresholds=QualityThresholds(100.0, 1.0, 254.0, 1.0),
                width=96,
            )

            cap = cv2.VideoCapture(str(audit))
            try:
                self.assertTrue(cap.isOpened())
                self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 4)
            finally:
                cap.release()

    def test_write_filtered_video_has_no_overlay_and_uses_selected_frames_only(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame_paths = []
            colors = [30, 180]
            for i, color in enumerate(colors):
                image = np.full((64, 96, 3), color, dtype=np.uint8)
                frame_path = tmp_path / f"frame_{i:06d}.png"
                self.assertTrue(cv2.imwrite(str(frame_path), image))
                frame_paths.append(frame_path)

            selected = [
                SelectedFrame(i, i, i / 5.0, QualityMetrics(1.0, 100.0, 20.0), frame_paths[i])
                for i in range(2)
            ]
            output = tmp_path / "filtered.mp4"
            write_filtered_video(selected, output, fps=5.0, width=96)

            cap = cv2.VideoCapture(str(output))
            try:
                self.assertTrue(cap.isOpened())
                self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 2)
                ok, first = cap.read()
                self.assertTrue(ok)
                self.assertLess(abs(float(first.mean()) - colors[0]), 8.0)
            finally:
                cap.release()

    def test_write_selected_frames_txt_records_source_indices_and_paths(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            selected = [
                SelectedFrame(3, 0, 0.3, QualityMetrics(1.0, 100.0, 20.0), tmp_path / "frame_000000_src_000003.jpg"),
                SelectedFrame(5, 1, 0.5, QualityMetrics(1.0, 100.0, 20.0), tmp_path / "frame_000001_src_000005.jpg"),
            ]
            output = tmp_path / "selected_frames.txt"

            write_selected_frames_txt(output, selected)

            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "output_index\tsource_index\ttimestamp_sec\tpath\tsha256")
            self.assertIn("0\t3\t0.300000", lines[1])
            self.assertIn("1\t5\t0.500000", lines[2])

    def test_write_run_manifest_records_reproducible_inputs_and_parameters(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "run_manifest.json"
            thresholds = QualityThresholds(10.0, 20.0, 245.0, 8.0)

            write_run_manifest(
                output,
                video_path=Path("data/user-video/test.mp4"),
                output_dir=Path("outputs/test_clear_frames"),
                selected_frames_path=Path("outputs/test_clear_frames/selected_frames.txt"),
                report_path=Path("outputs/test_clear_frames/frame_report.csv"),
                summary_path=Path("outputs/test_clear_frames/summary.json"),
                filtered_video_path=Path("outputs/test_filtered_clean.mp4"),
                src_fps=16.0,
                total_frames=100,
                selected_count=96,
                thresholds=thresholds,
                args={"selection": "quality_filter", "sharpness_quantile": 0.10},
            )

            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"]["video"], "data/user-video/test.mp4")
            self.assertEqual(manifest["source"]["frames"], 100)
            self.assertEqual(manifest["outputs"]["selected_frames"], "outputs/test_clear_frames/selected_frames.txt")
            self.assertEqual(manifest["parameters"]["selection"], "quality_filter")
            self.assertEqual(manifest["thresholds"]["min_sharpness"], 10.0)

    def test_manifest_and_summary_distinguish_sampling_from_quality_drops(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            thresholds = QualityThresholds(10.0, 20.0, 245.0, 8.0)
            candidates = [
                FrameCandidate(i * 10, float(i), QualityMetrics(100.0, 120.0, 30.0))
                for i in range(10)
            ]
            selected = [
                SelectedFrame(candidate.index, output_index, candidate.timestamp_sec, candidate.quality, None)
                for output_index, candidate in enumerate(candidates[:8])
            ]

            summary_path = tmp_path / "summary.json"
            write_summary_json(
                summary_path,
                video_path=Path("input/test.mp4"),
                src_fps=30.0,
                total_frames=100,
                candidates=candidates,
                selected=selected,
                thresholds=thresholds,
                target_fps=5.0,
                scan_fps=3.0,
            )

            manifest_path = tmp_path / "run_manifest.json"
            write_run_manifest(
                manifest_path,
                video_path=Path("input/test.mp4"),
                output_dir=tmp_path / "frames",
                selected_frames_path=tmp_path / "frames" / "selected_frames.txt",
                report_path=tmp_path / "frames" / "frame_report.csv",
                summary_path=summary_path,
                filtered_video_path=None,
                src_fps=30.0,
                total_frames=100,
                analyzed_count=len(candidates),
                selected_count=len(selected),
                thresholds=thresholds,
                args={"scan_fps": 3.0, "selection": "quality_filter"},
            )

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(summary["source_frames"], 100)
            self.assertEqual(summary["analyzed_candidates"], 10)
            self.assertEqual(summary["quality_dropped_candidates"], 2)
            self.assertEqual(summary["sampling_skipped_frames"], 90)
            self.assertEqual(summary["retention_ratio"], 0.8)
            self.assertEqual(summary["source_retention_ratio"], 0.08)

            selection = manifest["selection"]
            self.assertEqual(selection["source_frames"], 100)
            self.assertEqual(selection["analyzed_candidates"], 10)
            self.assertEqual(selection["dropped_frames"], 2)
            self.assertEqual(selection["quality_dropped_candidates"], 2)
            self.assertEqual(selection["sampling_skipped_frames"], 90)
            self.assertEqual(selection["retention_ratio"], 0.8)
            self.assertEqual(selection["source_retention_ratio"], 0.08)


if __name__ == "__main__":
    unittest.main()
