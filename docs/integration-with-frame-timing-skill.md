# Integration With frame-timing-skill

The intended split is:

1. `video-frame-preprocess`: convert raw video into clean, model-safe frames.
2. `frame-timing-skill`: adjust frame timing for reconstruction and presentation pacing.
3. `lingbot-map`: consume the final frame sequence for point-cloud reconstruction.

Example chain:

```bash
video-frame-preprocess \
  --video input/test1.mp4 \
  --output runs/test1/clean_frames \
  --scan_fps 0 \
  --selection quality_filter \
  --clean

frame-timing \
  runs/test1/clean_frames \
  --artifact-root runs/test1/timing \
  --write

python demo.py \
  --image_folder runs/test1/timing/output_frames
```

The second command is illustrative. Keep the final CLI contract aligned with the actual `frame-timing-skill` project.
