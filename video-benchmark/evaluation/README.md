# CPU video evaluation in this cloud environment

Tested on the two **Round 3 grandmother speaking clips**, Wan 2.6 I2V Flash and PixVerse V6. Originals are unchanged. No new video generation, video uploads, API evaluation fees or GPU charges.

The prepared Python environment is `/workspace/video-eval-venv`. It uses four CPU cores of quota and 32 GiB RAM, with no GPU. Source checkouts, official weights and caches are under `/workspace/video-eval-tools`. The benchmark's separate API runtime and spending ledger are untouched.

## Working tools

- FFmpeg/ffprobe and OpenCV: decoded-frame, black/freeze, audio and technical checks.
- faster-whisper 1.2.1, `small.en`, CPU int8: transcription and word timestamps, no expected-text prompt.
- WhisperX 3.8.6: same ASR backend, official Silero VAD and English wav2vec2 forced alignment. Recognition agreement is not independent model corroboration.
- SyncNet V2: official S3FD face detection, tracking/cropping and 25 fps audio/video synchronization; verified with a deliberately injected 200 ms delay.
- DOVER and FAST-VQA: full trained checkpoint inference on CPU. Both correctly assign substantially lower scores to a deliberately blurred/degraded local derivative.
- VBench: **only the official temporal-flickering dimension**, run from pinned source on CPU. Full VBench installation requires CUDA and the full suite was not run. The blur control demonstrates that this flicker score alone can improve when visual quality gets worse.

Read [the report](../results/economy_round3/evaluation/report.md), or extract the complete media ZIP and open `video-benchmark/results/economy_round3/evaluation/index.html`.

## Run in the existing environment

From `video-benchmark/`, use `/workspace/video-eval-venv/bin/python` for:

```text
evaluation/basic_checks.py
evaluation/speech_checks.py faster_whisper
evaluation/speech_checks.py whisperx
evaluation/sync_checks.py
evaluation/learned_visual.py dover
evaluation/learned_visual.py fastvqa
evaluation/learned_visual.py vbench
evaluation/learned_visual.py dover --negative-control
evaluation/learned_visual.py fastvqa --negative-control
evaluation/learned_visual.py vbench --negative-control
evaluation/tool_manifest.py
evaluation/report.py
```

Control runs require `/workspace/video-eval-tools/quality-control.mp4`, generated locally with:

```sh
ffmpeg -hide_banner -loglevel error -y \
  -i results/economy_round3/speech/wan_flash.mp4 \
  -vf 'scale=90:160,scale=720:1280:flags=neighbor,boxblur=10:1' \
  -c:v libx264 -crf 38 -threads 2 -an \
  /workspace/video-eval-tools/quality-control.mp4
```

Scripts write measured results to `results/economy_round3/evaluation/`; none calls API Mart. The original generation ledger stays private and is not needed to view reports.

## Installation and compatibility record

`environment-freeze.txt` records all installed Python packages. `results/economy_round3/evaluation/environment.json` records upstream URLs, exact Git commits, weight hashes, CPU versions and compatibility adaptations. Local editable source paths in the freeze refer to the prepared environment; the freeze alone is not a turnkey installer for another OS.

A fresh environment needs Python 3.12, FFmpeg, and an isolated venv. Install CPU `torch==2.8.0+cpu`, `torchvision==0.23.0+cpu`, `torchaudio==2.8.0+cpu` from `https://download.pytorch.org/whl/cpu`, followed by the recorded speech/image dependencies. Important pins are `numpy==2.3.5`, `faster-whisper==1.2.1`, `whisperx==3.8.6`, `transformers==4.57.6`, `huggingface-hub==0.36.2`, and `torchcodec==0.7.0`.

Clone the exact upstream commits in the manifest. DOVER and FAST-VQA are installed editable with `pip install --no-deps --no-build-isolation -e PATH`; their old metadata conflicts with the modern CPU environment even though tested inference works. `openai-clip` provides `clip`, and `scikit-video` provides `skvideo`; do not install the unrelated PyPI `clip` package. DOVER's old torch 1.13 pin has no Python 3.12 wheel. Its complete official checkpoint is loaded strictly, replacing all model tensors; the redundant ImageNet initialization download is skipped. The model architecture and published scoring formula are retained.

WhisperX's official Silero source is cloned locally, avoiding an unnecessary GitHub API metadata request. Official NLTK `punkt_tab` resources from `nltk/nltk_data` are cached in `/workspace/video-eval-tools/nltk_data`. faster-whisper receives FFmpeg-decoded mono 16 kHz PCM to avoid a PyAV 19 file-opening incompatibility. Audio is not denoised, normalized or replaced.

Weight sources:

- SyncNet/S3FD: `https://www.robots.ox.ac.uk/~vgg/software/lipsync/data/` (`syncnet_v2.model`, `sfd_face.pth`).
- DOVER: official GitHub release linked in the DOVER README, `DOVER.pth`.
- FAST-VQA: official release linked in its README, `FAST_VQA_B_1_4.pth`.
- ASR: `Systran/faster-whisper-small.en` on Hugging Face, exact revision in manifest.
- Alignment: torchaudio's English wav2vec2 ASR weights, downloaded from its official PyTorch source.

Network access now works for the configured sources. Added custom hosts: `huggingface.co`, `www.robots.ox.ac.uk`, `us.aws.cdn.hf.co`; package-manager/GitHub/PyTorch domains use the existing preset. No credentials are needed for these public models.

## License distinction

SyncNet and faster-whisper code are MIT; WhisperX is BSD-2-Clause; VBench is Apache-2.0 with component-specific terms. **DOVER and FAST-VQA use S-Lab non-commercial licenses.** Commercial use requires contacting their contributors. Model weights and bundled components can have separate terms. Upstream code and weights are not redistributed in this results ZIP.
