#!/usr/bin/env python3
"""Transcribe native speech, align words, and render word-highlighted captions."""
import os
os.environ.update(HF_HUB_DISABLE_XET='1',HF_HOME='/workspace/video-eval-tools/hf',MPLCONFIGDIR='/tmp/video-eval-mpl',XDG_CACHE_HOME='/workspace/video-eval-tools/cache',TORCH_HOME='/workspace/video-eval-tools/torch',NLTK_DATA='/workspace/video-eval-tools/nltk_data')
import argparse,json,re,math,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;FOLDER=ROOT/'results/shepherd_round4'

def escape(text):return text.replace('\\','\\\\').replace('{','\\{').replace('}','\\}').replace('\n',' ')
def timestamp(t):
 n=round(t*100);return f'{n//360000}:{n//6000%60:02d}:{n//100%60:02d}.{n%100:02d}'
def phrases(words):
 groups=[];chunk=[]
 for w in words:
  if chunk and (len(chunk)>=7 or len(' '.join(x['word'] for x in chunk+[w]))>44):groups.append(chunk);chunk=[]
  chunk.append(w)
  if len(chunk)>=3 and re.search(r'[.!?]$',w['word']):groups.append(chunk);chunk=[]
 if chunk:
  if len(chunk)==1 and groups and len(groups[-1])>3:chunk.insert(0,groups[-1].pop())
  groups.append(chunk)
 return groups

def build_ass(words,duration=15):
 header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Speech,DejaVu Sans,62,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,110,110,72,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
 events=[];groups=phrases(words)
 for group in groups:
  start=max(0,group[0]['start']);end=min(duration,group[-1]['end'])
  bounds=sorted(set(round(min(end,max(start,t)),2) for w in group for t in [w['start'],w['end']]))
  for a,z in zip(bounds,bounds[1:]):
   if z<=a:continue
   mid=(a+z)/2;active=next((i for i,w in enumerate(group) if w['start']<=mid<w['end']),None)
   parts=[]
   for i,w in enumerate(group):
    text=escape(w['word'])
    parts.append(('{\\c&H0000FFFF&}'+text+'{\\c&H00FFFFFF&}') if i==active else text)
   text=' '.join(parts);events.append(dict(start=a,end=z,active_word=group[active]['word'] if active is not None else None,text=text))
 return header+''.join(f'Dialogue: 0,{timestamp(e["start"])},{timestamp(e["end"])},Speech,,0,0,0,,{e["text"]}\n' for e in events),events

def align():
 import torch,whisperx
 torch.set_num_threads(4)
 original=torch.hub.load
 def local(*args,**kwargs):
  if kwargs.get('repo_or_dir')=='snakers4/silero-vad':kwargs.update(repo_or_dir='/workspace/video-eval-tools/silero-vad',source='local')
  return original(*args,**kwargs)
 torch.hub.load=local
 try:model=whisperx.load_model('small.en',device='cpu',compute_type='int8',language='en',vad_method='silero',download_root='/workspace/video-eval-tools/weights',threads=4)
 finally:torch.hub.load=original
 source=FOLDER/'landscape/pixverse.mp4';audio=whisperx.load_audio(str(source));transcript=model.transcribe(audio,batch_size=4,language='en')
 am,metadata=whisperx.load_align_model(language_code='en',device='cpu',model_dir='/workspace/video-eval-tools/weights/alignment')
 result=whisperx.align(transcript['segments'],am,metadata,audio,'cpu',return_char_alignments=False)
 words=result['word_segments']
 if not words or any(not all(k in w for k in ['word','start','end']) for w in words):raise RuntimeError('Missing actual-speech word timing; do not fabricate captions')
 previous=0
 for w in words:
  if not all(math.isfinite(w[k]) for k in ['start','end']) or not 0<=w['start']<w['end']<=15.1 or w['start']<previous-.03:raise RuntimeError('Invalid aligned word timing; manual reconciliation required')
  previous=w['end']
 data=dict(transcript=' '.join(s['text'].strip() for s in transcript['segments']),words=words,segments=result['segments'],model='WhisperX small.en CPU int8 + English wav2vec2 alignment',initial_prompt=None,method='Unprompted transcription of the native generated audio; captions contain actual recognized speech, not blindly inserted requested words.')
 (FOLDER/'speech-alignment.json').write_text(json.dumps(data,indent=2)+'\n');print('Actual speech:',data['transcript'],flush=True);return data

def audio_digest(p):
 data=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-t','15','-map','0:a:0','-c:a','copy','-f','adts','-'])
 return hashlib.sha256(data).hexdigest()

def render(data):
 source=FOLDER/'landscape/pixverse.mp4';target=FOLDER/'shepherd-captioned-15s.mp4'
 ass,events=build_ass(data['words']);(FOLDER/'captions.ass').write_text(ass);(FOLDER/'caption-events.json').write_text(json.dumps(events,indent=2)+'\n')
 # ASS filename is controlled, relative to cwd, and contains no user-supplied filter syntax.
 ass_path=(FOLDER/'captions.ass').relative_to(ROOT).as_posix()
 vf=f'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,ass={ass_path}'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-map','0:v:0','-map','0:a:0','-t','15','-vf',vf,'-c:v','libx264','-preset','medium','-crf','18','-threads','4','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(target)],cwd=ROOT,check=True)
 before,after=audio_digest(source),audio_digest(target)
 if before!=after:raise RuntimeError('Caption export changed native audio packets in the delivery interval')
 import benchmark as b
 metrics=b.analyze_video(target)
 if (metrics['width'],metrics['height'])!=(1920,1080) or abs(metrics['duration_seconds']-15)>.09 or not metrics['audio_present']:raise RuntimeError('Captioned delivery dimensions/duration/audio failed validation')
 validation=dict(technical=metrics,audio_packets_unchanged=True,audio_adts_sha256=after,caption_words=len(data['words']),caption_events=len(events),word_timing_source='WhisperX forced alignment of actual native audio',timing_granularity_seconds=.01,first_word_start=data['words'][0]['start'],last_word_end=data['words'][-1]['end'],captioned_file=target.name)
 (FOLDER/'caption-validation.json').write_text(json.dumps(validation,indent=2)+'\n');print('Captioned delivery validated:',target,flush=True)

def main():
 global FOLDER
 p=argparse.ArgumentParser();p.add_argument('command',choices=['align','render','all']);p.add_argument('--round',choices=['shepherd_round4','replicate_shepherd_round5'],default='shepherd_round4');a=p.parse_args()
 FOLDER=ROOT/'results'/a.round
 data=align() if a.command in ['align','all'] else json.loads((FOLDER/'speech-alignment.json').read_text())
 if a.command in ['render','all']:render(data)
if __name__=='__main__':main()
