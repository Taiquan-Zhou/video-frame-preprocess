# Design Notes

## Problem Split

The original reconstruction workflow mixed several concerns:

- video frame extraction;
- bad-frame filtering;
- frame timing edits for static or fast camera motion;
- reconstruction training;
- browser-based visualization and video export.

This project isolates the first two concerns. The goal is to produce reliable, clean frame sequences that can be reviewed, versioned, uploaded, and passed into later timing or modeling stages.

## Decisions

- Keep model input frames clean. Do not draw debug text, metrics, or overlays onto images used for modeling.
- Prefer conservative filtering. Removing too many frames can create sparse or unstable point clouds.
- Preserve source cadence by default with `--scan_fps 0`; timing changes should happen later.
- Emit manifests and CSV reports so every preprocessing run is reproducible.
- Keep frame timing policy outside this repository. Fast-motion duplication and static-frame deletion belong to `frame-timing-skill`.

## Planned Automation

A future agent can analyze a single source video and propose a two-stage strategy:

1. preprocessing strategy: extract frames, remove blurry or over/under-exposed frames, detect low-quality spans;
2. timing strategy: detect long static spans, detect fast camera motion, recommend frame deletion or duplication ranges.

Pure algorithmic detection can handle most objective metrics, but subjective presentation quality still benefits from human review or a vision-language agent.
