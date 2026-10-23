# Replicate PixVerse V6: 15-second shepherd comparison

**Same exact prompt, adapted opening-frame bytes, 15-second duration, 1080p request and native audio as the API Mart shepherd test.** Both original user photographs informed that adapted frame; neither test passed the original photographs as two separate model inputs.

Replicate published output price: **USD 0.23/second**, estimated **USD 3.45** for this run. A 25% safety allowance was reserved within the user-reported USD 6.74 credit. Provider metering reports 15.042 output seconds, corresponding to approximately **USD 3.46** at that rate (unrounded estimate USD 3.45966). Actual billed charge and remaining account credit are **not exposed by the prediction response** and are not claimed as verified.

API Mart baseline was billed USD 1.20. Replicate published price for the equivalent settings is 2.875× that amount. No paid retries were made.

## Actual recognized speech

Panic scatters the flock. You don't bring sheep home by shouting. Learn the land, earn their trust, and lead them calmly. On this farm, patience fills the pen and feeds the family.

## Captioned delivery

1920×1080 landscape, approximately 15 seconds. White phrase text with the currently spoken word highlighted yellow, timed by unprompted recognition and WhisperX forced alignment of this new native audio. No copied timings from the prior take. Native AAC audio packets in the delivery interval are preserved unchanged. Editable ASS and actual word-level timing JSON included.

## Reference and comparison limits

16:9 opening frame adapted by image generation from the two user-supplied chat photographs (hillside shepherd and farmhouse sheep pen); original attachments were visible in chat but not exposed as local files. No claim that adapted pixels are the original files.

This compares provider offerings using the same advertised model family and equivalent explicit parameters. No fixed seed was specified; sampling and hidden provider defaults/model revisions may differ. Visual differences between two single takes do not establish a provider quality ranking.

## Included files

- shepherd-captioned-15s.mp4: final delivery.
- landscape/pixverse.mp4: unchanged native Replicate output.
- captions.ass: editable highlight captions.
- speech-alignment.json: actual transcript and word timing.
- caption-validation.json: audio preservation and delivery metrics.
- pricing.json: official price evidence and source.
- model-schema.json: verified supported inputs.
- index.html: offline player.

CLI: `python3 replicate_shepherd.py resume` resumes the existing prediction; it never generates a replacement. Replicate uses a separate private `.runtime/replicate-state.json`; it must not be reset or mixed with the API Mart ledger. Missing private state plus public submitted results blocks regeneration. Private prediction IDs, temporary output URLs, reference upload URLs and credentials are excluded.
