# Round 3 automatic evaluation

Two Round 3 grandmother speaking clips, original native MP4s unchanged. Wildlife clips not evaluated in this pass.

Additional API/evaluation spend: **$0**. No new generation.

| Metric | Wan 2.6 I2V Flash | PixVerse V6 |
|---|---|---|
| faster-whisper word error rate | 0% | 0% |
| WhisperX word error rate | 0% | 0% |
| First aligned word | 0.550 s | 0.658 s |
| Last aligned word ends | 5.837 s | 5.755 s |
| SyncNet estimated audio delay | 0 ms | 40 ms |
| SyncNet confidence | 7.068 | 5.721 |
| SyncNet best-offset minimum distance | 8.807 | 8.577 |
| DOVER normalized visual score | 0.878 | 0.880 |
| FAST-VQA normalized visual score | 0.926 | 0.929 |
| VBench flicker dimension (motion-confounded) | 0.976 | 0.975 |
| Black frames / detected freezes | 0 / 0 | 0 / 0 |

## Recognized speech

**Wan 2.6 I2V Flash:** At 70, I climbed Kilimanjaro. They said I couldn't, I did.

**PixVerse V6:** At 70, I climbed Kilimanjaro, they said I couldn't, I did.

## Interpretation and validation

Both recognizers recover the requested words. WER ignores case/punctuation, expands contractions and treats 70 as seventy. Neither receives the expected sentence as an initial prompt. WhisperX uses the same faster-whisper backend and small.en weights, so agreement is not independent corroboration.

SyncNet estimates zero audio delay for Wan and 40 ms of audio delay for PixVerse. Evaluation uses official face tracking/cropping at 25 fps, giving 40 ms temporal granularity. These are encouraging global synchronization estimates, not proof of perfect mouth shapes or every phoneme matching. Confidence is a distance contrast, not a percentage. Minimum distance is at the best searched lag; these values are not a universal pass/fail test.

Both clips start speech later than the prompt requested: first aligned word at 0.550 s and 0.658 s, versus a requested start by 0.2 s. Word alignment itself has uncertainty, especially around silence.

DOVER and FAST-VQA results are close and do not establish a meaningful winner from one clip per model. Their normalized 0–1 outputs are model-specific calibrations, not probabilities, percentages of human approval or interchangeable scales. Neither checks speech or lip synchronization.

Known-delay control passed: adding exactly 200 ms of audio delay changes SyncNet offset from 0 to -5 frames, the expected -200 ms under its sign convention.

Degraded-video controls passed: deliberate low-resolution blur drops DOVER from 0.878 to 0.093 and FAST-VQA from 0.926 to 0.109. Controls use local derivatives, never regenerated or replaced originals.

VBench limitation demonstrated: the same blur increases its flicker score from 0.976 to 0.997. Its official flicker metric assumes static videos; smoothing and legitimate motion confound it. Only this CPU-compatible dimension ran. Full VBench installation requires CUDA; no full VBench overall score is claimed.

FFmpeg/OpenCV found no black frames, exact duplicate runs or FFmpeg freeze events at the stated thresholds. Edge sharpness and brightness are recorded in basic.json as heuristics, not overall visual quality.

All processing ran locally on CPU. No videos were uploaded to evaluation services; no extra API Mart generation, paid evaluation API or GPU charges. Model/code downloads used public upstream sources.

Licenses: SyncNet code is MIT; faster-whisper is MIT and WhisperX is BSD-2-Clause; VBench is Apache-2.0 with component-specific terms. DOVER and FAST-VQA repositories use the S-Lab non-commercial license; commercial use requires contacting contributors. Inspect upstream model-weight terms separately before deploying these tools commercially.

Compatibility: DOVER declares old torch 1.13 dependencies; this environment uses CPU torch 2.8.0, torchvision 0.23.0 and torchaudio 2.8.0 on Python 3.12. Actual inference and degradation controls passed with strict checkpoint loading. DOVER redundant ImageNet initialization is skipped because all weights are replaced by the complete DOVER checkpoint. FAST-VQA uses openai-clip/scikit-video providers for legacy module names. VBench runs from pinned source. Silero is loaded from its official local clone. FFmpeg decodes audio for faster-whisper to avoid an incompatible PyAV 19 file-reader argument. See environment.json and the installed-package freeze for exact versions.

## Evidence and reproducibility

[Interactive report](index.html) · [Machine-readable summary](summary.json) · [Environment and source commits](environment.json). Raw tool JSON and FFmpeg/SyncNet logs are in this folder. Scripts and installed-package freeze are in `../../../evaluation/`. Official model weights and cloned upstream repositories remain in the prepared cloud environment, excluded from Git/ZIP.

Run using `/workspace/video-eval-venv/bin/python`: `evaluation/basic_checks.py`, `evaluation/speech_checks.py faster_whisper`, `evaluation/speech_checks.py whisperx`, `evaluation/sync_checks.py`, `evaluation/learned_visual.py dover`, `evaluation/learned_visual.py fastvqa`, `evaluation/learned_visual.py vbench`, then `evaluation/report.py`. Start in video-benchmark/. Full setup details: [evaluation README](../../../evaluation/README.md).
