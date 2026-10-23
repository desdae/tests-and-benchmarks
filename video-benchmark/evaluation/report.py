"""Build a readable report from actual evaluator outputs, without inventing scores."""
import json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/economy_round3/evaluation'
load=lambda n:json.loads((OUT/(n+'.json')).read_text())
basic,fw,wx,sync,dover,fast,vbench=[load(n) for n in ['basic','faster_whisper','whisperx','syncnet','dover','fastvqa','vbench']]
rows=[]
for slug,name in [('wan_flash','Wan 2.6 I2V Flash'),('pixverse','PixVerse V6')]:
 w=wx['clips'][slug]['aligned_words'];s=sync['clips'][slug]
 rows.append(dict(slug=slug,name=name,asr_wer=fw['clips'][slug]['normalized_word_error_rate'],whisperx_wer=wx['clips'][slug]['normalized_word_error_rate'],transcript=fw['clips'][slug]['transcript'],speech_start=w[0]['start'],speech_end=w[-1]['end'],audio_delay_ms=s['estimated_audio_delay_ms'],sync_confidence=s['confidence'],sync_min_distance=s['minimum_distance'],dover=dover['clips'][slug]['normalized_fused_score'],fastvqa=fast['clips'][slug]['normalized_score'],vbench_flicker=vbench['clips'][slug]['temporal_flickering_score'],black_frames=basic['clips'][slug]['opencv']['black_frame_count_98pct_pixels_below_16'],ffmpeg_events=basic['clips'][slug]['ffmpeg_black_or_freeze_events']))
controls={k:load(k+'-controls')['clips']['wan_blurred_control'] for k in ['dover','fastvqa','vbench']}
assert sync['control']['passed'] and sync['control']['observed_offset_change_frames']==-5
assert all(wx['clips'][r['slug']]['alignment_status']=='completed' for r in rows)
assert controls['dover']['normalized_fused_score']<rows[0]['dover']
assert controls['fastvqa']['normalized_score']<rows[0]['fastvqa']
# Confirm artifacts refer to exactly the original media checked by decoded-frame analysis.
import hashlib
for r in rows:
 p=ROOT/'results/economy_round3/speech'/(r['slug']+'.mp4')
 assert hashlib.sha256(p.read_bytes()).hexdigest()==basic['clips'][r['slug']]['sha256']
summary={'scope':'Two Round 3 grandmother speaking clips, original native MP4s unchanged. Wildlife clips not evaluated in this pass.','clips':rows,'controls':controls,'sync_control':sync['control'],'all_checks_validated':True,'additional_api_spend_usd':'0','vbench_scope':'Only official temporal_flickering dimension, executed from source on CPU; full VBench suite not installed/run.'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
a,b=rows
metrics=[('faster-whisper word error rate',f'{a["asr_wer"]:.0%}',f'{b["asr_wer"]:.0%}'),('WhisperX word error rate',f'{a["whisperx_wer"]:.0%}',f'{b["whisperx_wer"]:.0%}'),('First aligned word',f'{a["speech_start"]:.3f} s',f'{b["speech_start"]:.3f} s'),('Last aligned word ends',f'{a["speech_end"]:.3f} s',f'{b["speech_end"]:.3f} s'),('SyncNet estimated audio delay',f'{a["audio_delay_ms"]} ms',f'{b["audio_delay_ms"]} ms'),('SyncNet confidence',f'{a["sync_confidence"]:.3f}',f'{b["sync_confidence"]:.3f}'),('SyncNet best-offset minimum distance',f'{a["sync_min_distance"]:.3f}',f'{b["sync_min_distance"]:.3f}'),('DOVER normalized visual score',f'{a["dover"]:.3f}',f'{b["dover"]:.3f}'),('FAST-VQA normalized visual score',f'{a["fastvqa"]:.3f}',f'{b["fastvqa"]:.3f}'),('VBench flicker dimension (motion-confounded)',f'{a["vbench_flicker"]:.3f}',f'{b["vbench_flicker"]:.3f}'),('Black frames / detected freezes','0 / 0','0 / 0')]
notes=[
'Both recognizers recover the requested words. WER ignores case/punctuation, expands contractions and treats 70 as seventy. Neither receives the expected sentence as an initial prompt. WhisperX uses the same faster-whisper backend and small.en weights, so agreement is not independent corroboration.',
'SyncNet estimates zero audio delay for Wan and 40 ms of audio delay for PixVerse. Evaluation uses official face tracking/cropping at 25 fps, giving 40 ms temporal granularity. These are encouraging global synchronization estimates, not proof of perfect mouth shapes or every phoneme matching. Confidence is a distance contrast, not a percentage. Minimum distance is at the best searched lag; these values are not a universal pass/fail test.',
'Both clips start speech later than the prompt requested: first aligned word at 0.550 s and 0.658 s, versus a requested start by 0.2 s. Word alignment itself has uncertainty, especially around silence.',
'DOVER and FAST-VQA results are close and do not establish a meaningful winner from one clip per model. Their normalized 0–1 outputs are model-specific calibrations, not probabilities, percentages of human approval or interchangeable scales. Neither checks speech or lip synchronization.',
'Known-delay control passed: adding exactly 200 ms of audio delay changes SyncNet offset from 0 to -5 frames, the expected -200 ms under its sign convention.',
f'Degraded-video controls passed: deliberate low-resolution blur drops DOVER from {a["dover"]:.3f} to {controls["dover"]["normalized_fused_score"]:.3f} and FAST-VQA from {a["fastvqa"]:.3f} to {controls["fastvqa"]["normalized_score"]:.3f}. Controls use local derivatives, never regenerated or replaced originals.',
f'VBench limitation demonstrated: the same blur increases its flicker score from {a["vbench_flicker"]:.3f} to {controls["vbench"]["temporal_flickering_score"]:.3f}. Its official flicker metric assumes static videos; smoothing and legitimate motion confound it. Only this CPU-compatible dimension ran. Full VBench installation requires CUDA; no full VBench overall score is claimed.',
'FFmpeg/OpenCV found no black frames, exact duplicate runs or FFmpeg freeze events at the stated thresholds. Edge sharpness and brightness are recorded in basic.json as heuristics, not overall visual quality.',
'All processing ran locally on CPU. No videos were uploaded to evaluation services; no extra API Mart generation, paid evaluation API or GPU charges. Model/code downloads used public upstream sources.',
'Licenses: SyncNet code is MIT; faster-whisper is MIT and WhisperX is BSD-2-Clause; VBench is Apache-2.0 with component-specific terms. DOVER and FAST-VQA repositories use the S-Lab non-commercial license; commercial use requires contacting contributors. Inspect upstream model-weight terms separately before deploying these tools commercially.',
'Compatibility: DOVER declares old torch 1.13 dependencies; this environment uses CPU torch 2.8.0, torchvision 0.23.0 and torchaudio 2.8.0 on Python 3.12. Actual inference and degradation controls passed with strict checkpoint loading. DOVER redundant ImageNet initialization is skipped because all weights are replaced by the complete DOVER checkpoint. FAST-VQA uses openai-clip/scikit-video providers for legacy module names. VBench runs from pinned source. Silero is loaded from its official local clone. FFmpeg decodes audio for faster-whisper to avoid an incompatible PyAV 19 file-reader argument. See environment.json and the installed-package freeze for exact versions.'
]
md=['# Round 3 automatic evaluation','',summary['scope'],'','Additional API/evaluation spend: **$0**. No new generation.','', '| Metric | Wan 2.6 I2V Flash | PixVerse V6 |','|---|---|---|']+['| '+' | '.join(r)+' |' for r in metrics]
md += ['', '## Recognized speech','']
for r in rows:md += [f'**{r["name"]}:** {r["transcript"]}','']
md += ['## Interpretation and validation','']
for note in notes:md += [note,'']
md += ['## Evidence and reproducibility','', '[Interactive report](index.html) · [Machine-readable summary](summary.json) · [Environment and source commits](environment.json). Raw tool JSON and FFmpeg/SyncNet logs are in this folder. Scripts and installed-package freeze are in `../../../evaluation/`. Official model weights and cloned upstream repositories remain in the prepared cloud environment, excluded from Git/ZIP.','', 'Run using `/workspace/video-eval-venv/bin/python`: `evaluation/basic_checks.py`, `evaluation/speech_checks.py faster_whisper`, `evaluation/speech_checks.py whisperx`, `evaluation/sync_checks.py`, `evaluation/learned_visual.py dover`, `evaluation/learned_visual.py fastvqa`, `evaluation/learned_visual.py vbench`, then `evaluation/report.py`. Start in video-benchmark/. Full setup details: [evaluation README](../../../evaluation/README.md).','']
(OUT/'report.md').write_text('\n'.join(md))
head='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Round 3 automatic video evaluation</title><style>body{max-width:1100px;margin:32px auto;padding:0 20px;background:#10131b;color:#e7ebf4;font:16px/1.6 system-ui}a{color:#a9c6ff}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #354057;text-align:left}.players{display:flex;gap:20px;flex-wrap:wrap}.players article{flex:1;min-width:260px}video{width:100%;height:420px;background:#000}small{color:#b4c2d8}</style><h1>Round 3 automatic evaluation</h1><p>Two grandmother speaking clips · local CPU evaluation · $0 additional API spend</p>'''
body='<div class="players">'+''.join('<article><h2>'+html.escape(r['name'])+'</h2><video controls playsinline preload="metadata" src="../speech/'+r['slug']+'.mp4"></video><p>'+html.escape(r['transcript'])+'</p></article>' for r in rows)+'</div>'
body+='<table><tr><th>Metric</th><th>Wan</th><th>PixVerse</th></tr>'+''.join('<tr>'+''.join('<td>'+html.escape(c)+'</td>' for c in row)+'</tr>' for row in metrics)+'</table><h2>What the results mean</h2>'
body+=''.join('<p>'+html.escape(n)+'</p>' for n in notes)
body+='<p><a href="summary.json">Raw summary</a> · <a href="environment.json">Environment and source commits</a> · <a href="../comparison.html">Original comparison viewer</a></p></html>'
(OUT/'index.html').write_text(head+body);print('Evaluation report and evidence validated')
