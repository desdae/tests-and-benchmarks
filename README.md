# AI video quality benchmark

Completed reference-guided pilot: **four real videos**—café speech and fox/music on Wan 3.0 and MiniMax H3, with each model's native audio.

**API Mart charges: $1.22872.** Last observed account balance: $8.77128. The original $6 spending authorization was shared across the run.

## Download and compare

Download [video-benchmark-results.zip](https://github.com/desdae/tests-and-benchmarks/raw/refs/heads/main/video-benchmark-results.zip), extract it, and open:

```text
video-benchmark/results/reference/comparison.html
```

The ZIP contains all four original MP4s, two synthetic reference images, detailed timed prompts, contact sheets, technical metrics, cost reports, the interactive viewer, implementation and tests. It contains no API key or private runtime state.

Wan output is 720×1280 at 30 fps, approximately 5.04 seconds. MiniMax output is 768×1344 at 24 fps, approximately 5.18 seconds—near, but not exactly, 9:16. All four clips contain AAC audio. Qualitative scores, exact spoken wording, lip synchronization and sound-event alignment remain pending playback review.

The original eight-video text-only benchmark remains separate and incomplete. This pilot uses opening-frame references and detailed prompts on two models, rather than claiming all four models were tested.

## Source and execution safety

See [the benchmark README](video-benchmark/README.md), [pilot report](video-benchmark/results/reference/report.md), and [detailed prompts](video-benchmark/config/reference-tests.json).

Individual media files are Git-ignored; the explicitly requested downloadable ZIP carries them. Private `.runtime/state.json` is retained only in the original environment and excluded from Git and the ZIP. A fresh clone/archive must not silently start a new spending ledger or regenerate these clips. The client blocks when completed public results exist but the private ledger is missing. Restore the original private state securely before resuming live operations. Existing reports, the HTML viewer and media work without the private state.
