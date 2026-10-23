# AI video benchmarks

## Latest: Shorts/Reels presenter layouts

**Four new real videos** test **Veo 3.1 Quality Official** and **Kling V4**, each in two compositions using fresh synthetic presenter references:

- **Full vertical:** a normal full-screen speaker shot.
- **Infographic layout:** a speaker positioned in the lower half, with the upper half clear.

All delivery exports are **1080×1920 (9:16)**. The infographic versions have a uniform solid navy upper region (rows 0–959) ready for overlays. The full presenter head remains below that line in sampled frames. Each model generates its own native speech; all four export audio streams are bit-for-bit copies of their sources.

**New-round API Mart charges: $3.816**, within the explicitly authorized additional $6. **Latest available balance: $4.95528.** Combined charges including the previous pilot: $5.04472.

[Download the new round bundle](https://github.com/desdae/tests-and-benchmarks/raw/refs/heads/main/shorts-round2-results.zip)

Extract the whole ZIP and open:

```text
video-benchmark/results/shorts_round2/comparison.html
```

The bundle contains four original native MP4s, four delivery exports, both reference stills, complete prompts, contact sheets, technical metrics, current pricing, cost reports, validation, the interactive viewer, implementation and tests. Original native outputs remain unchanged. Veo is native 1080p; Kling is native 720p and its delivery exports are upscaled. Clips last approximately four seconds.

See [the new report](video-benchmark/results/shorts_round2/report.md), [prompts and layout configuration](video-benchmark/config/shorts-round2.json), and [validation](video-benchmark/results/shorts_round2/validation.json).

These are two premium model candidates, not an independently established best-model ranking. Representative frames were visually inspected; exact spoken wording, lip synchronization and qualitative scores remain pending playback review. Manual scoring is available in the viewer.

## Previous reference-guided pilot

Four real café-speech and fox/music videos on Wan 3.0 and MiniMax H3, with each model's native audio. **Previous pilot cost: $1.22872.**

[Download the previous pilot bundle](https://github.com/desdae/tests-and-benchmarks/raw/refs/heads/main/video-benchmark-results.zip) · [Previous pilot report](video-benchmark/results/reference/report.md)

For that archive, open `video-benchmark/results/reference/comparison.html`. Wan output is 720×1280 at 30 fps, approximately 5.04 seconds; MiniMax is 768×1344 at 24 fps, approximately 5.18 seconds—near 9:16. The original eight-video text-only benchmark remains separate and incomplete.

## Source and spending safety

See [the benchmark README](video-benchmark/README.md). **40 implementation tests pass**, including sequential submission, budget boundaries, no-duplicate spending, account conversion, native audio control selection, FFmpeg media extraction, exact export dimensions, unchanged audio and upper-half uniformity.

Individual media are Git-ignored; the explicitly requested downloadable ZIPs carry them. API keys, temporary result URLs, private task IDs and `.runtime/state.json` are excluded from Git and archives. The original cloud environment retains the shared ledger. A fresh clone/archive must not silently regenerate these clips or create a new spending ledger over completed public results; the client blocks that operation. Restore the original private state securely before resuming live operations. The viewer and media work without private state or API keys.

The original authorization was $6; a further $6 was explicitly authorized only for the new round. Each round retains its own cap and the 25% safety margin; the private ledger preserves previous reservations. No deposits or automatic recharge were enabled.
