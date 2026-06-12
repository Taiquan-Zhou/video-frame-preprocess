import csv
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from video_frame_preprocess.batch import BatchConfig, BatchResult, load_config, run_one, write_batch_summary


class BatchPipelineTest(unittest.TestCase):
    def test_load_config_merges_defaults_with_file_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "input_dir": "data/user-video",
                        "output_dir": "outputs",
                        "sharpness_quantile": 0.05,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.input_dir, Path("data/user-video"))
            self.assertEqual(config.output_dir, Path("outputs"))
            self.assertEqual(config.sharpness_quantile, 0.05)
            self.assertEqual(config.selection, "quality_filter")

    def test_write_batch_summary_outputs_stable_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "batch_summary.csv"
            results = [
                BatchResult(
                    video="test1.mp4",
                    source_frames=100,
                    selected_frames=96,
                    dropped_frames=4,
                    retention_ratio=0.96,
                    output_dir="outputs/test1_clear_frames",
                    filtered_video="outputs/test1_filtered_clean.mp4",
                    manifest="outputs/test1_clear_frames/run_manifest.json",
                    success=True,
                    error="",
                )
            ]

            write_batch_summary(summary_path, results)

            with summary_path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["video"], "test1.mp4")
            self.assertEqual(rows[0]["selected_frames"], "96")
            self.assertEqual(rows[0]["success"], "1")

    def test_run_one_processes_real_small_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            output_dir = tmp_path / "outputs"
            input_dir.mkdir()
            video_path = input_dir / "sample.mp4"

            writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (96, 64))
            self.assertTrue(writer.isOpened())
            try:
                for i in range(6):
                    image = np.full((64, 96, 3), 40 + i * 25, dtype=np.uint8)
                    cv2.putText(image, str(i), (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                    writer.write(image)
            finally:
                writer.release()

            config = BatchConfig(
                input_dir=input_dir,
                output_dir=output_dir,
                selection="quality_filter",
                scan_fps=0.0,
                sharpness_quantile=0.0,
                max_drop_ratio=1.0,
                max_consecutive_drops=6,
                image_ext="jpg",
                write_filtered_video=True,
            )

            result = run_one(video_path, config)

            self.assertTrue(result.success, result.error)
            self.assertEqual(result.video, "sample.mp4")
            self.assertEqual(result.source_frames, 6)
            self.assertGreater(result.selected_frames, 0)
            self.assertTrue(Path(result.output_dir).is_dir())
            self.assertTrue(Path(result.manifest).is_file())
            self.assertTrue(Path(result.filtered_video).is_file())
            self.assertEqual(len(list(Path(result.output_dir).glob("frame_*_src_*.jpg"))), result.selected_frames)


if __name__ == "__main__":
    unittest.main()
