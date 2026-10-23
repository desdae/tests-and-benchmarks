#!/usr/bin/env python3
"""Package the shepherd video, actual caption timing, prompt and provenance."""
import json,html,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent;F=ROOT/'results/shepherd_round4'
def main():
 r=json.loads((F/'results.json').read_text());c=json.loads((F/'caption-validation.json').read_text());a=json.loads((F/'speech-alignment.json').read_text());cfg=json.loads((ROOT/'config/shepherd-round4.json').read_text())
 r.update(delivery=c,actual_transcript=a['transcript'],captioned_file='shepherd-captioned-15s.mp4',caption_timing_file='speech-alignment.json',caption_style='White phrase text with only the currently spoken word highlighted yellow; black outline/shadow; burned into video.',reference_provenance=cfg['reference_provenance'])
 (F/'results.json').write_text(json.dumps(r,indent=2)+'\n')
 report=['# The shepherd: 15-second PixVerse landscape test','',f'Actual API Mart generation charge: USD {r["known_actual_cost_usd"]}. Latest observed available balance: USD {r["remaining_balance_usd"]}.','',
 'Delivery: **1920×1080, 16:9 landscape, approximately 15 seconds**, with original model-generated voice and burned-in word-highlighted captions. All captioned-interval native AAC packets are copied unchanged. No external TTS or replacement voice.','',
 '## Actual recognized speech','',a['transcript'],'','## Requested script','',cfg['script'],'',
 '## Captions','',f'{c["caption_words"]} words aligned with WhisperX English forced alignment. Phrase text stays white; the currently spoken word is yellow. Captions follow unprompted recognition of actual generated audio. ASS timing is rounded to 10 ms; forced alignment itself is an estimate, not sample-accurate proof. Original native MP4 remains unchanged in landscape/pixverse.mp4.','',
 '## Reference and generation method','',cfg['reference_provenance'],'',cfg['mode_note'],'',
 'The 16:9 adapted opening preserves the user-reference shepherd, collie, flock, farmhouse and rustic pen in one spatially coherent scene. It is included as references/shepherd-round4-opening.png. The inspected 14.7-second frame shows the visible flock gathered inside the enclosure behind the closed wooden gate, with the shepherd and collie in the foreground and farmhouse at right.','',
 '## Files','',
 '- shepherd-captioned-15s.mp4: delivery with highlighted captions.\n- landscape/pixverse.mp4: unchanged original native output.\n- captions.ass: editable word-highlight caption source.\n- speech-alignment.json: actual transcript and word timing.\n- caption-events.json: each display/highlight interval.\n- caption-validation.json: audio/dimensions/duration checks.\n- results.json: public generation and delivery metadata.\n- index.html: offline player.','',
 'The shared spending ledger, task IDs, temporary result URLs and credentials are excluded. No paid generation retries. Resume the same known task with `python3 shepherd_video.py resume`; never regenerate to replace missing private state.','']
 (F/'report.md').write_text('\n'.join(report))
 page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The shepherd — PixVerse test</title><style>body{max-width:1100px;margin:30px auto;padding:0 20px;background:#10131b;color:#e7ebf4;font:16px/1.6 system-ui}video{display:block;width:100%;background:#000}a{color:#a9c6ff}details{margin:20px 0}pre{white-space:pre-wrap}img{max-width:100%}</style><h1>The shepherd</h1><p>15-second landscape · PixVerse V6 · native speech · word-highlighted captions</p><video controls playsinline preload="metadata" src="shepherd-captioned-15s.mp4"></video><p><a href="shepherd-captioned-15s.mp4" download>Download captioned MP4</a> · <a href="landscape/pixverse.mp4">Original native output</a> · <a href="captions.ass">Editable captions</a> · <a href="report.md">Report</a></p>'''
 page+='<h2>Actual recognized speech</h2><p>'+html.escape(a['transcript'])+'</p><details><summary>Detailed prompt and reference provenance</summary><pre>'+html.escape(cfg['prompt'])+'</pre><p>'+html.escape(cfg['reference_provenance'])+'</p><img src="../../references/shepherd-round4-opening.png" alt="Adapted landscape opening frame"></details></html>'
 (F/'index.html').write_text(page)
 files=[p for p in F.rglob('*') if p.is_file()]
 files += [ROOT/f for f in ['shepherd_video.py','caption_shepherd.py','deliver_shepherd.py','benchmark.py','reference_tests.py','config/models.json','config/shepherd-round4.json','references/shepherd-round4-opening.png']]
 target=ROOT.parent/'shepherd-pixverse-15s.zip'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('README.md','Extract everything and open video-benchmark/results/shepherd_round4/index.html. Captioned 1080p landscape MP4, native original, editable captions, actual word timing, prompt, adapted reference frame and public reports included. No private generation ledger or credentials. Caption words follow the native generated speech.\n')
  for p in sorted(set(files)):z.write(p,Path('video-benchmark')/p.relative_to(ROOT))
 print('Bundle:',target,'bytes:',target.stat().st_size)
if __name__=='__main__':main()
