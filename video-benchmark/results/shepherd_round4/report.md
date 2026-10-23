# The shepherd: 15-second PixVerse landscape test

Actual API Mart generation charge: USD 1.2. Latest observed available balance: USD 2.87208.

Delivery: **1920×1080, 16:9 landscape, approximately 15 seconds**, with original model-generated voice and burned-in word-highlighted captions. All captioned-interval native AAC packets are copied unchanged. No external TTS or replacement voice.

## Actual recognized speech

Panic scatters the flock. You don't bring sheep home by shouting. Learn the land, earn their trust, and lead them calmly. On this farm, patience fills the pen and feeds the family.

## Requested script

Panic scatters the flock. You don't bring sheep home by shouting. Learn the land, earn their trust, and lead them calmly. On this farm, patience fills the pen and feeds the family.

## Captions

32 words aligned with WhisperX English forced alignment. Phrase text stays white; the currently spoken word is yellow. Captions follow unprompted recognition of actual generated audio. ASS timing is rounded to 10 ms; forced alignment itself is an estimate, not sample-accurate proof. Original native MP4 remains unchanged in landscape/pixverse.mp4.

## Reference and generation method

16:9 opening frame adapted by image generation from the two user-supplied chat photographs (hillside shepherd and farmhouse sheep pen); original attachments were visible in chat but not exposed as local files. No claim that adapted pixels are the original files.

15-second image-to-video from adapted landscape opening frame. Exact first/last-frame transition mode only supports 5/8 seconds and is not used.

The 16:9 adapted opening preserves the user-reference shepherd, collie, flock, farmhouse and rustic pen in one spatially coherent scene. It is included as references/shepherd-round4-opening.png. The inspected 14.7-second frame shows the visible flock gathered inside the enclosure behind the closed wooden gate, with the shepherd and collie in the foreground and farmhouse at right.

## Files

- shepherd-captioned-15s.mp4: delivery with highlighted captions.
- landscape/pixverse.mp4: unchanged original native output.
- captions.ass: editable word-highlight caption source.
- speech-alignment.json: actual transcript and word timing.
- caption-events.json: each display/highlight interval.
- caption-validation.json: audio/dimensions/duration checks.
- results.json: public generation and delivery metadata.
- index.html: offline player.

The shared spending ledger, task IDs, temporary result URLs and credentials are excluded. No paid generation retries. Resume the same known task with `python3 shepherd_video.py resume`; never regenerate to replace missing private state.
