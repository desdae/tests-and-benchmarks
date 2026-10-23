# API Mart native-audio video benchmark

Python 3.11+; no third-party Python dependencies. FFmpeg and ffprobe are required for media analysis and contact sheets. Run commands from this directory. Use the existing isolated cloud checkout; do not create a Git worktree.

## Current execution status

API Mart authentication and read-only account access work after environment publication. The existing `APIMART_API_KEY` Network secret is used securely; no key is printed, stored or archived.

The original eight-video text-only benchmark remains incomplete. Its all-eight public-price estimate is **$5.14870**, assuming Gemini's UI 10-second estimate, or **$6.435875** with the required 25% margin, above the $6 authorization. Token-settled Gemini/Seedance maximum charges remain uncertain. The original prompts/configuration are retained separately.

The new **reference-guided pilot** tests Wan 3.0 and MiniMax H3 on café speech and fox movement with two synthetic opening-frame references and detailed timed prompts. See `results/reference/report.md` and `results/reference/comparison.html` for live results and actual costs; `reference_tests.py` uses the SAME $6 spending ledger. Current public fixed-duration prices are fetched before execution, with conservative authorization at the higher undiscounted rate plus 25%. Expected four-clip billing is $1.22872; conservative authorization is $1.919875. No new paid generation is automatically repeated.

Cloud networking allows the API and official documentation pages. A draft also adds the observed media CDN hostname `getapib.org`; publish the environment settings to apply that destination if downloads are still blocked. A completed generation is retained as `download_pending` when transfer is blocked, with task ID and original URL stored privately. Other already-authorized generations can continue sequentially after verified successful generation; `python3 reference_tests.py resume` retries downloads without paid POSTs. Never add the API key as a CDN credential.

## Commands

```bash
python3 -m unittest discover -s tests -v
python3 benchmark.py fetch-docs  # no generation, saves official pages privately
python3 benchmark.py dry-run    # writes all eight estimates or explicit skips
python3 benchmark.py preflight  # documented read-only authentication/balance check
python3 benchmark.py execute    # dry run, authenticate, sequential paid requests
python3 benchmark.py resume     # ONLY polls/downloads already tracked task IDs
python3 benchmark.py analyze    # FFprobe, loudness/silence, contact sheets
python3 benchmark.py report
python3 benchmark.py package    # ../video-benchmark-results.zip
```

`--poll-seconds` accepts 5–10 (default 7). `--timeout` is a per-task polling deadline, default 1800 seconds. Every network operation has an HTTP timeout. Only safe API GETs retry (three attempts); paid POSTs are never retried. No command deposits credits or enables recharge.

## Documentation gate — required before live execution

The initial documentation review is recorded in the configuration. After the key is restored, have the implementation agent refresh `https://docs.apimart.ai/llms.txt` and the four official model pages listed in `config/models.json`, follow their endpoint links, and resolve the remaining charge/reservation bounds using official pricing/account evidence. Fetching pages alone does not verify them. Do not mark verification true without inspecting the evidence. If a requested model does not exist or does not support native audio, record a skip; do not substitute it.

Each model needs:

- `verified_at`: current UTC ISO timestamp; verification expires after 24 hours.
- `evidence`: `sources` (official documentation URLs), plus boolean confirmations for `availability`, `parameters`, `native_audio`, `pricing`, `reservation_bound`, `duration_bound`. Include textual `pricing_basis` and `parameter_notes` to explain the documented bounds and controls. Unknown bounds must remain null and the model must be skipped.
- `request_template`: the **documented** request object with exact `model` ID and `prompt: "{prompt}"`. Only that top-level prompt placeholder is replaced. Specify the supported portrait, resolution, native audio, watermark and duration controls; include only documented fields. All requests must produce one video. Reference inputs and separate audio generation are prohibited. No duration field should be supplied for Gemini if it has no such documented control.
- `estimate_usd`, `maximum_charge_usd`, `maximum_reservation_usd`: nonnegative USD decimal strings for one video, including audio and every billable component. Reservation must conservatively cover the final maximum charge. Include maximum natural duration, rounding, and provider credit-to-USD conversion in the evidence when relevant. Never infer billing from a marketing price without confirming the endpoint and resolution.
- `output_duration_upper_bound_seconds`: finite documented bound, including Gemini's natural-duration output. An unbounded token/duration charge or unknown reservation means **skip**.
- Clear `skip_reason` for unsupported, unavailable or unbounded requests.

The shared `api` object contains `verified_at`, `evidence.sources` and confirmations for `authentication`, `response_formats`, `read_only_probe`, `billing`. Bearer authentication is documented; live authentication still needs the key. The documented probe is `/v1/balance` and requires `success: true`. The account balance `/v1/user/balance` uses `remain_credits / 10`, avoiding configurable `remain_balance` units. The smaller of account balance and limited-token quota is used; unlimited tokens do not override the account balance. The `/v1/usage` query records the provider's default last-24-hour USD spending, no more than once per minute. Its cache/reconciliation lag is disclosed; it is not treated as per-job billing.

Response mappings are RFC 6901 JSON pointers, including array indices when necessary: `submission_task_id_pointer`, `task_status_pointer`, `video_url_pointer`, optional `actual_cost_pointer` with `actual_cost_currency: "USD"`. Set documented `statuses.pending`, `statuses.completed`, and `statuses.failed` arrays. Do not assume a particular response envelope. A missing required field stops execution and preserves existing state. This generic adapter must be adjusted and tested if official response/auth formats are incompatible; it is not claimed to be verified against the live API.

Re-run tests, `dry-run`, and `preflight` after verification. Dry-run prints every test's estimate, maximum and skip status; unverified values remain null, never zero-priced. A full verified plan above $6 with the 25% margin is skipped in its entirety. Unsupported models remain explicit skips. Execute only the verified bounded subset if one or more requested models are unavailable.

## Spending and interruption safety

The hard client authorization is $6.00. Each job reserves `1.25 × max(maximum charge, maximum reservation)` in the local authorization ledger **before** its paid POST. The full remaining plan must fit the remaining authorization and available provider balance when supported. Failed jobs and refunds never replenish the local authorization automatically. Actual billing is reported separately; balance differences are not attributed to a job. This cannot enforce a provider-side billing cap or prevent another client spending the account's credits.

`.runtime/state.json` is mode 0600 inside a mode 0700 directory. Writes are atomic and fsynced, with a single-process advisory lock. It contains task IDs, temporary result URLs, per-job costs, hashes, and checkpoints, never the key or Authorization header. Keep it across restarts and protect it as private state. A crash between paid submission and receiving a task ID produces an unresolved `submitting` intent. A timeout, HTTP failure or malformed submission response becomes `submission_unknown`. Both block all further paid jobs. Reconcile with the provider; never delete the ledger or start in a fresh directory to bypass it. No automatic regeneration occurs after failure.

`resume` makes no paid POSTs. It polls the same tasks and refreshes completed-task URLs before downloading, so expired original URLs can be recovered if the provider still retains the job. CDN requests use HTTPS and **never** carry API authorization. If blocked, the required hostname is reported and the task ID/original URL stay private. Add that exact hostname to the environment allowlist and resume. MP4 downloads use a temporary file and atomic rename. Audio provenance is established through verified native-audio request controls; FFprobe only establishes whether an audio stream is present.

## Results and assessment

`results/{speech,music}/{wan3,minimax_h3,gemini_omni,seedance25}.mp4` hold original downloads; adjacent JPEGs contain six sampled frames. JSON/CSV reports distinguish planned, skipped, pending, failed, completed, and unknown submissions. Missing metrics and billing remain unknown. FFmpeg checks duration, dimensions, codecs, frame rate, audio presence/sample rate, mean dBFS and silence percentage (−40 dB, 0.1 second minimum), plus file size. No aesthetic scores or lip-sync claims are inferred from these metrics.

Open `results/comparison.html` directly in a browser. It embeds result metadata and needs no server, API key or external resources. Keep it next to the `speech/` and `music/` folders when moving it. It has two test tabs, a 2×2 model grid, native playback controls, group play/pause and mute controls, synchronized starts/seeking, technical information, contact sheets, manual weighted scores and a leaderboard. Browser storage on file URLs varies: export scores to JSON to keep them reliably. Scores and ranking require all six categories; the overall ranking requires both tests. All qualitative assessment starts pending human review.

`video-benchmark-results.zip` includes implementation, tests and public results/media. It excludes private task state, cached documentation, environment files and secrets. Media and private state are ignored by Git; reports/code are reviewable. A bundle without videos is a blocked benchmark deliverable, not a completed benchmark.

## Validation evidence

The test suite includes simulated sequential submissions, interruption/CDN recovery, no-duplicate-spending checks, documented array response parsing, account credit conversion, usage throttling, FFmpeg extraction on audible/silent/audio-free synthetic clips, and browser checks for tabs, scoring, weighted ranking, mute controls, score export and persistence. Synthetic fixtures are temporary and never appear as model outputs. Browser validation uses an internal temporary loopback server because managed Chromium blocks file-URL navigation; the viewer itself has no server dependency.

## Reference-guided pilot

A separate `reference_tests.py` pilot uses two original synthetic portrait references and expanded timed prompts in `config/reference-tests.json`: café speech and a fox crossing three stones. It tests Wan 3.0 at 720P and MiniMax H3 at 768P, both with native audio and fixed five-second output. These image-to-video requests intentionally differ from the original text-only benchmark; they do not count toward its eight-video completion. The generated references are in `references/` and included in result archives but ignored by Git. Their generation used the image-generation tool, not API Mart video credits.

From this directory: `python3 reference_tests.py dry-run`, `python3 reference_tests.py execute`, or `python3 reference_tests.py resume`. The pilot uses the SAME private state and $6 authorization ledger as `benchmark.py`, so changing workflows does not reset the spending limit. `resume` issues no paid generation POST. New paid jobs use current public pricing, a higher undiscounted-rate ceiling and a 25% margin; balance is checked immediately after submission for unexpected reservations. Downloads, metrics, a viewer with reference images/prompts, and reports are in `results/reference/`. No new paid submission is repeated automatically.

### Completed pilot

All four reference-guided generations have succeeded and their original MP4s are downloaded. Actual API Mart cost: **$1.22872**; latest available balance: **$8.77128**. All clips have native AAC audio. Wan outputs 720×1280 at 30 fps, 5.038 s; MiniMax outputs 768×1344 at 24 fps, 5.184 s (near 9:16, not exact). The CDN is reachable in the current instance; retain the saved network allowance for future tasks. All 40 implementation tests pass. Contact sheets were visually inspected; qualitative scores, exact wording, lip sync and audio-event alignment remain pending playback review in the comparison viewer.

A delivered archive or fresh Git clone cannot run CLI operations over completed public results without the original private ledger; this prevents accidental duplicate paid generation after downloading the bundle. The standalone viewer and reports remain usable.

## Shorts/Reels round two

The next round uses fresh synthetic presenter references in two compositions: normal full-screen portrait, and a lower-positioned presenter with the upper half clear for infographics. Both outputs are full **9:16**. Models: **Veo 3.1 Quality Official** at native 1080p and **Kling V4** at native 720p; four-second clips with native speech. These are premium candidates, not an independently proven quality ranking.

The user authorized **up to $6 additional** for this round. Its own client cap is $6 with the 25% margin, separate from the original round while sharing the same private ledger; the combined authorization ceiling is $12. The current four-clip estimate is $3.816, with $5.9625 conservatively reserved at undiscounted rates plus margin. Actual results and charges are in `results/shorts_round2/`.

```bash
python3 shorts_tests.py dry-run
python3 shorts_tests.py execute  # only with the existing ledger and authorization
python3 shorts_tests.py resume   # no paid generation POSTs
python3 shorts_tests.py export
python3 shorts_tests.py report
python3 shorts_tests.py package
```

Both original native outputs and exact **1080×1920** delivery exports are retained. Full-screen clips are scaled/padded without cropping. Lower-positioned exports have a solid #101827 upper 960-pixel region, suitable for infographic overlays. Native audio is copied without replacement. Kling exports are upscaled from 720p; the report distinguishes native and delivery resolution. Export validation checks canvas size, audio presence and decoded upper-half luma uniformity on every frame; sampled contact sheets still need visual review for presenter placement and any clipping. All qualitative/lip-sync scores remain pending actual playback review.

Fresh-clone execution is blocked when completed public results exist but the private ledger is missing; restore the original environment state rather than silently duplicating paid work. The new archive is `../shorts-round2-results.zip` and contains only this new round's media/references/reports and reusable code, not the previous pilot's media.

### Completed Shorts/Reels round

All four new native clips and all four exact 1080×1920 delivery exports are complete. Actual new-round API Mart charges: **$3.816**. Latest available balance: **$4.95528**. Both lower-layout exports have a uniform upper 960-pixel region verified across every decoded frame, and sampled frames show the complete presenter head below that line. All four delivery audio bitstreams match their native sources exactly. Original files, export files, current prices, prompts, references, validation and the standalone comparison viewer are in the new round bundle. These checks do not establish exact spoken wording, lip synchronization or an aesthetic winner; manual review remains available in the viewer.
