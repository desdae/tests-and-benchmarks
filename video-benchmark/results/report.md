# API Mart video benchmark

Generated: 2026-10-23T08:35:45.403341+00:00

Completed videos: 0/8. Paid submissions or uncertain attempts: 4.
Known billed total: $1.22872; billing complete.
Conservative committed authorization (including 25% margin): $1.9198750 / $6.00.
Remaining provider balance: 8.771280000000002.

Displayed-price estimate for all requested jobs: $5.14870; with 25% margin: $6.4358750. This estimate is not a verified maximum charge or reservation.

## Execution limitations

- All-eight displayed-price estimate exceeds $6 after the required 25% safety margin; no full-plan spending is authorized.

Additional image-guided jobs tracked in the same spending ledger: 4. These do not count toward the original eight text-only clips. See [reference pilot report](reference/report.md) and [reference comparison](reference/comparison.html). The known billed total above includes these additional jobs.

| Test/model | Status | Estimated USD | Billed USD | Detail |
|---|---|---|---|---|
| speech/wan3 | skipped | 0.32875 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. Market Gold/current rate 0.6575 credits/s = $0.06575/s; 5 s = $0.32875. Highest displayed Official rate 0.8219 credits/s gives $0.41095 for 5s. Documentation bills requested fixed seconds; native audio same price. Initial reservation ceiling not documented, so no paid request is permitted. |
| speech/minimax_h3 | skipped | 0.28560 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. Market Gold/current rate 0.5712 credits/s = $0.05712/s; 5 s = $0.2856. Highest displayed Official rate 0.714 credits/s implies $0.357, but reservation ceiling and a binding final billing upper bound were not established. |
| speech/gemini_omni | skipped | 0.88000 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. Market Gold/current 720P estimate 0.88 credits/s = $0.088/s; UI budgets 10 seconds = $0.88. Text input $1.2/M tokens and output $14/M tokens at Gold. Page documents a max-10-second preauthorization, then final reconciliation from actual token usage. The approximate 3-10s range and reservation estimate are not a guaranteed total charge ceiling. |
| speech/seedance25 | skipped | 1.08000 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. No-reference-video 720P Gold/current rate 2.16 credits/s = $0.216/s; 5 s = $1.08. Token unit price $10/M at 720P. Documentation says final settlement uses actual completion_tokens, refunds excess reservations or charges shortfall. No verified pixel/token upper bound for portrait was established. Auto-duration30s reservation is avoided, but a safe fixed-duration final charge/reservation ceiling is still unverified. |
| music/wan3 | skipped | 0.32875 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. Market Gold/current rate 0.6575 credits/s = $0.06575/s; 5 s = $0.32875. Highest displayed Official rate 0.8219 credits/s gives $0.41095 for 5s. Documentation bills requested fixed seconds; native audio same price. Initial reservation ceiling not documented, so no paid request is permitted. |
| music/minimax_h3 | skipped | 0.28560 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. Market Gold/current rate 0.5712 credits/s = $0.05712/s; 5 s = $0.2856. Highest displayed Official rate 0.714 credits/s implies $0.357, but reservation ceiling and a binding final billing upper bound were not established. |
| music/gemini_omni | skipped | 0.88000 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. Market Gold/current 720P estimate 0.88 credits/s = $0.088/s; UI budgets 10 seconds = $0.88. Text input $1.2/M tokens and output $14/M tokens at Gold. Page documents a max-10-second preauthorization, then final reconciliation from actual token usage. The approximate 3-10s range and reservation estimate are not a guaranteed total charge ceiling. |
| music/seedance25 | skipped | 1.08000 | unavailable | Paid execution blocked: initial reservation and/or final token-settled charge cannot yet be bounded from the reviewed documentation. No-reference-video 720P Gold/current rate 2.16 credits/s = $0.216/s; 5 s = $1.08. Token unit price $10/M at 720P. Documentation says final settlement uses actual completion_tokens, refunds excess reservations or charges shortfall. No verified pixel/token upper bound for portrait was established. Auto-duration30s reservation is avoided, but a safe fixed-duration final charge/reservation ceiling is still unverified. |

## Human assessment rubric

Score each category from 1 to 10 after watching and listening:

- Visual realism: 25%
- Motion quality: 25%
- Prompt adherence: 20%
- Temporal consistency: 15%
- Audio quality and synchronization: 10%
- Cost efficiency: 5%

All qualitative scores remain pending. Inspect exact speech, lip synchronization, eye and face motion, three landings and synchronized notes, anatomy, music, effects, ambience, continuity, and native audio.

Technical audio metrics use FFmpeg volumedetect mean dBFS and silencedetect at -40 dB for at least 0.1 seconds. They do not measure perceived quality or synchronization. Contact sheets are representative frames, not a temporal quality judgment. Generation elapsed time includes provider queue and polling latency.

Gemini Omni duration is variable; no duration field is assumed. Unsupported model IDs are never substituted.
Budget accounting retains the full conservative reservation after failure or refund. Actual costs are populated only from documented USD billing fields; balance deltas are not treated as per-job billing.

## Resume

From video-benchmark/: `python3 benchmark.py resume` polls existing known task IDs only; `python3 benchmark.py execute` resumes outstanding tasks before considering unsent jobs. A submission with an unknown outcome blocks all new jobs until manually reconciled with the provider. Do not delete `.runtime/state.json` to bypass this protection.
