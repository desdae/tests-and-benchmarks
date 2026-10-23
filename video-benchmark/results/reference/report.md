# Reference-guided API Mart pilot

Completed: 4/4 selected videos.
Known billed total for this four-clip pilot: $1.22872.
Latest available account/token minimum balance: $4.9552800000000005.
Pilot conservative authorization committed: $1.9198750 of $6.00. All rounds combined: $7.8823750 of $12.00 authorized.

This is a separate image-to-video pilot, not the original eight text-only benchmark videos. Two synthetic opening-frame references and expanded timed prompts are used consistently across Wan3 and MiniMax H3. Gemini and Seedance were not included in this bounded pilot. No separate TTS/music/audio service was used.

| Clip | Status | Billed USD | Duration | Dimensions | Audio |
|---|---|---|---|---|---|
| speech/wan3 | completed | 0.32876 | 5.038005 | 720×1280 | True |
| speech/minimax_h3 | completed | 0.2856 | 5.184 | 768×1344 | True |
| speech/gemini_omni | skipped | — | — | —×— | — |
| speech/seedance25 | skipped | — | — | —×— | — |
| music/wan3 | completed | 0.32876 | 5.038005 | 720×1280 | True |
| music/minimax_h3 | completed | 0.2856 | 5.184 | 768×1344 | True |
| music/gemini_omni | skipped | — | — | —×— | — |
| music/seedance25 | skipped | — | — | —×— | — |

## Review

All six qualitative rubric scores remain pending human review. Inspect the actual clips and native audio for exact wording, lip sync, three synchronized landings/notes, anatomy, face identity and continuity. Contact sheets and loudness cannot establish these qualities.

Input references are stored in ../../references/. Detailed prompts: ../../config/reference-tests.json. Original MP4 downloads are unchanged. Private shared task IDs/result URLs are in ../../.runtime/state.json (excluded from archives).

Resume from video-benchmark/ with `python3 reference_tests.py resume`. It never issues a paid generation POST. Execute checks existing ledger keys before submitting any new job; never delete the shared ledger to rerun. The $6 authorization is shared with benchmark.py, not reset for this pilot.

Pricing uses live public default payable rates for estimates and the higher undiscounted rates for maximum client authorization, plus 25%. One MiniMax input image is within its documented free-image allowance. Reservation is estimated from the fixed-duration price; the balance is read immediately after submission and new jobs stop on an unexpectedly large decrease. A client cannot enforce a provider-side billing cap.
