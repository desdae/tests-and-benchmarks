#!/usr/bin/env python3
"""Package the Replicate shepherd result without exposing private task state."""
import json,html,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent;F=ROOT/'results/replicate_shepherd_round5'
API_VIDEO='https://github.com/desdae/tests-and-benchmarks/raw/df76043cd65ecc6b8d40bbe270001952d6ad3a1d/shepherd-pixverse-captioned-15s.mp4'
def main():
 r=json.loads((F/'results.json').read_text());cfg=json.loads((ROOT/'config/replicate-shepherd-round5.json').read_text());a=json.loads((F/'speech-alignment.json').read_text());v=json.loads((F/'caption-validation.json').read_text());q=json.loads((F/'pricing.json').read_text())
 r.update(actual_transcript=a['transcript'],delivery=v,captioned_file='shepherd-captioned-15s.mp4',pricing=q,apimart_baseline_actual_cost_usd='1.20',same_prompt_as_apimart=True,same_adapted_reference_bytes_as_apimart=True)
 (F/'results.json').write_text(json.dumps(r,indent=2)+'\n')
 md=['# Replicate PixVerse V6: 15-second shepherd comparison','',
 '**Same exact prompt, adapted opening-frame bytes, 15-second duration, 1080p request and native audio as the API Mart shepherd test.** Both original user photographs informed that adapted frame; neither test passed the original photographs as two separate model inputs.','',
 f'Replicate published output price: **USD {q["usd_per_second"]}/second**, estimated **USD {r["job"]["estimated_cost_usd"]}** for this run. A 25% safety allowance was reserved within the user-reported USD 6.74 credit. Provider metering reports 15.042 output seconds, corresponding to approximately **USD 3.46** at that rate (unrounded estimate USD 3.45966). Actual billed charge and remaining account credit are **not exposed by the prediction response** and are not claimed as verified.','',
 'API Mart baseline was billed USD 1.20. Replicate published price for the equivalent settings is 2.875× that amount. No paid retries were made.','',
 '## Actual recognized speech','',a['transcript'],'',
 '## Captioned delivery','',
 '1920×1080 landscape, approximately 15 seconds. White phrase text with the currently spoken word highlighted yellow, timed by unprompted recognition and WhisperX forced alignment of this new native audio. No copied timings from the prior take. Native AAC audio packets in the delivery interval are preserved unchanged. Editable ASS and actual word-level timing JSON included.','',
 '## Reference and comparison limits','',cfg['reference_provenance'],'',
 'This compares provider offerings using the same advertised model family and equivalent explicit parameters. No fixed seed was specified; sampling and hidden provider defaults/model revisions may differ. Visual differences between two single takes do not establish a provider quality ranking.','',
 '## Included files','',
 '- shepherd-captioned-15s.mp4: final delivery.\n- landscape/pixverse.mp4: unchanged native Replicate output.\n- captions.ass: editable highlight captions.\n- speech-alignment.json: actual transcript and word timing.\n- caption-validation.json: audio preservation and delivery metrics.\n- pricing.json: official price evidence and source.\n- model-schema.json: verified supported inputs.\n- index.html: offline player.','',
 'CLI: `python3 replicate_shepherd.py resume` resumes the existing prediction; it never generates a replacement. Replicate uses a separate private `.runtime/replicate-state.json`; it must not be reset or mixed with the API Mart ledger. Missing private state plus public submitted results blocks regeneration. Private prediction IDs, temporary output URLs, reference upload URLs and credentials are excluded.','']
 (F/'report.md').write_text('\n'.join(md))
 page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Replicate shepherd comparison</title><style>body{max-width:1100px;margin:30px auto;padding:0 20px;background:#10131b;color:#e7ebf4;font:16px/1.6 system-ui}video{width:100%;background:#000}a{color:#a9c6ff}pre{white-space:pre-wrap}img{max-width:100%}</style><h1>Replicate: the shepherd</h1><p>PixVerse V6 · 15-second landscape · native voice · word-highlighted captions</p><video controls playsinline preload="metadata" src="shepherd-captioned-15s.mp4"></video><p><a href="shepherd-captioned-15s.mp4" download>Download captioned MP4</a> · <a href="landscape/pixverse.mp4">Native output</a> · <a href="captions.ass">Editable captions</a> · <a href="report.md">Report</a></p>'''
 page+='<p>Replicate requested-duration estimate: $3.45; reported-output-duration estimate: about $3.46. API Mart baseline billed: $1.20. Actual Replicate billing is not returned in the prediction response.</p><p><a href="'+API_VIDEO+'">Download the prior API Mart clip for comparison</a></p><h2>Actual recognized speech</h2><p>'+html.escape(a['transcript'])+'</p><details><summary>Identical prompt and reference provenance</summary><pre>'+html.escape(cfg['prompt'])+'</pre><p>'+html.escape(cfg['reference_provenance'])+'</p><img src="../../references/shepherd-round4-opening.png" alt="Same adapted opening reference as the prior take"></details></html>'
 (F/'index.html').write_text(page)
 items=[p for p in F.rglob('*') if p.is_file()]
 items += [ROOT/p for p in ['replicate_shepherd.py','caption_shepherd.py','deliver_replicate_shepherd.py','benchmark.py','config/replicate-shepherd-round5.json','references/shepherd-round4-opening.png']]
 target=ROOT.parent/'replicate-shepherd-15s.zip'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('README.md','Extract all files and open video-benchmark/results/replicate_shepherd_round5/index.html. Replicate PixVerse V6 provider test with the same prompt and adapted reference as the API Mart take. Native audio, locally aligned highlighted captions, editable ASS and word timing included. Official estimated price $3.45; actual account billing is not returned by prediction API. Private ledgers and credentials omitted.\n')
  for p in sorted(set(items)):z.write(p,Path('video-benchmark')/p.relative_to(ROOT))
 print('Bundle',target,'bytes',target.stat().st_size)
if __name__=='__main__':main()
