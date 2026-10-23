# AI video benchmarks

## Latest: 15-second shepherd story with highlighted captions

A **1920×1080 landscape PixVerse V6** video uses an opening frame adapted from the user's two shepherd/farm references. The hook, **“Panic scatters the flock,”** is spoken at approximately **0.13–1.31 seconds**. All 32 spoken words match the requested script under automatic recognition, and each is highlighted yellow as it is spoken while the surrounding phrase stays white.

The final sampled frame shows the flock behind a closed wooden gate beside the farmhouse, with the shepherd and border collie in front. Native audio is copied unchanged into the captioned delivery; output duration is exactly 15.0 seconds at 24 fps. Model native output was 1920×1072 and is padded to the exact 1920×1080 delivery canvas.

**API Mart generation charge: $1.20. Latest available balance: $2.87208.**

[Download captioned MP4](https://github.com/desdae/tests-and-benchmarks/raw/refs/heads/main/shepherd-pixverse-captioned-15s.mp4) · [Download complete bundle](https://github.com/desdae/tests-and-benchmarks/raw/refs/heads/main/shepherd-pixverse-15s.zip) · [Report and full script](video-benchmark/results/shepherd_round4/report.md)

The bundle includes the captioned clip, unchanged native output, editable ASS captions, actual transcript/word timing, detailed prompt, adapted reference and offline player. Extract all files and open `video-benchmark/results/shepherd_round4/index.html`.

## Economy models, grandmother and wildlife

Four real six-second vertical clips compare **Wan 2.6 I2V Flash** and **PixVerse V6**, each using the same new reference images and detailed prompts:

- A fictional 100-year-old African American grandmother recalls climbing Kilimanjaro at seventy.
- Two river otters beside a forest stream, including an entry into the water.

All outputs are native 720×1280 with native generated audio. No replacement speech or soundtrack.

**Round cost: $0.8832**. **Latest available balance: $4.07208**.

[Download the economy comparison bundle](https://github.com/desdae/tests-and-benchmarks/raw/refs/heads/main/economy-round3-results.zip)

Extract the complete ZIP and open `video-benchmark/results/economy_round3/comparison.html`.
The bundle includes four MP4s, both references, prompts, contact sheets, measured technical properties and a manual-scoring viewer. Automatic speech recognition, word alignment, SyncNet and CPU visual-quality checks are now available for the two grandmother clips. Both recognize the requested words; estimated audio delay is 0 ms for Wan and 40 ms for PixVerse. See the [automatic evaluation report](video-benchmark/results/economy_round3/evaluation/report.md). Human aesthetic review remains separate.

[Detailed report](video-benchmark/results/economy_round3/report.md) · [Prompts](video-benchmark/config/economy-round3.json)

## Previous round: Shorts/Reels presenter layouts

**Four new real videos** test **Veo 3.1 Quality Official** and **Kling V4**, each in two compositions using fresh synthetic presenter references:

- **Full vertical:** a normal full-screen speaker shot.
- **Infographic layout:** a speaker positioned in the lower half, with the upper half clear.

All delivery exports are **1080×1920 (9:16)**. The infographic versions have a uniform solid navy upper region (rows 0–959) ready for overlays. The full presenter head remains below that line in sampled frames. Each model generates its own native speech; all four export audio streams are bit-for-bit copies of their sources.

**New-round API Mart charges: $3.816**, within the explicitly authorized additional $6. **Balance after that round: $4.95528.** Combined charges including the previous pilot: $5.04472.

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
