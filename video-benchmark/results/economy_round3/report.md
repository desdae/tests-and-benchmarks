# Economy models: six-second reference tests

Completed 4/4. Actual billed USD: 0.8832. Latest available USD: 4.07208.

Both models receive the same fresh reference and detailed prompt for each scene. Native 720p vertical outputs with model-generated audio; no TTS or replacement soundtrack. The grandmother and her recollection are fictional.

| Scene | Model | Status | Billed USD |
|---|---|---|---|
| speech | wan2.6-i2v-flash | completed | 0.2016 |
| speech | pixverse-v6 | completed | 0.24 |
| nature | wan2.6-i2v-flash | completed | 0.2016 |
| nature | pixverse-v6 | completed | 0.24 |

Audio presence and technical metrics measured; exact speech, lip synchronization and naturalness require playback review.

Extract the whole archive and open comparison.html. Full prompts and references are included. No paid retries. Resume only existing task IDs with `python3 economy_tests.py resume`. Uses existing global $12 authorization, with a $1.38 conservative round cap.
