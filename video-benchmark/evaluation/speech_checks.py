"""CPU speech transcription, unprompted to avoid biasing exact-word evaluation."""
import os
os.environ.update(HF_HUB_DISABLE_XET='1',HF_HOME='/workspace/video-eval-tools/hf',MPLCONFIGDIR='/tmp/video-eval-mpl',XDG_CACHE_HOME='/workspace/video-eval-tools/cache',TORCH_HOME='/workspace/video-eval-tools/torch',NLTK_DATA='/workspace/video-eval-tools/nltk_data')
import json,time,re,sys,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/economy_round3/evaluation'
EXPECTED="At seventy, I climbed Kilimanjaro. They said I couldn't. I did."
def words(t):
 t=t.lower().replace("’", "'").replace("couldn't", "could not")
 return ["seventy" if w=="70" else w for w in re.findall(r"[a-z0-9]+(?:'[a-z]+)?",t)]
def wer(a,b):
 a,b=words(a),words(b);d=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  n=[i]
  for j,y in enumerate(b,1):n.append(min(n[-1]+1,d[j]+1,d[j-1]+(x!=y)))
  d=n
 return d[-1]/len(a)
kind=sys.argv[1];results={}
if kind=='faster_whisper':
 from faster_whisper import WhisperModel
 model=WhisperModel('small.en',device='cpu',compute_type='int8',cpu_threads=4,download_root='/workspace/video-eval-tools/weights')
else:
 import whisperx,torch
 # Use the official locally cloned Silero source, avoiding a redundant GitHub API metadata lookup.
 hub_load=torch.hub.load
 def local_silero(*args,**kwargs):
  if kwargs.get('repo_or_dir')=='snakers4/silero-vad':
   kwargs.update(repo_or_dir='/workspace/video-eval-tools/silero-vad',source='local')
  return hub_load(*args,**kwargs)
 torch.hub.load=local_silero
 model=whisperx.load_model('small.en',device='cpu',compute_type='int8',language='en',vad_method='silero',download_root='/workspace/video-eval-tools/weights',threads=4)
 torch.hub.load=hub_load
for slug in ['wan_flash','pixverse']:
 p=ROOT/'results/economy_round3/speech'/f'{slug}.mp4';start=time.monotonic()
 if kind=='faster_whisper':
  decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-f','f32le','-ac','1','-ar','16000','-'])
  audio=np.frombuffer(decoded,dtype=np.float32)
  seg,info=model.transcribe(audio,language='en',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False,temperature=0)
  segments=[dict(start=s.start,end=s.end,text=s.text,words=[dict(word=w.word,start=w.start,end=w.end,probability=w.probability) for w in s.words]) for s in seg]
  text=' '.join(s['text'].strip() for s in segments)
 else:
  audio=whisperx.load_audio(str(p));r=model.transcribe(audio,batch_size=4,language='en');segments=r['segments'];text=' '.join(s['text'].strip() for s in segments)
 result={'transcript':text,'normalized_word_error_rate':wer(EXPECTED,text),'exact_words_match':words(EXPECTED)==words(text),'segments':segments,'elapsed_seconds':round(time.monotonic()-start,3)}
 if kind=='whisperx':
  try:
   am,meta=whisperx.load_align_model(language_code='en',device='cpu',model_dir='/workspace/video-eval-tools/weights/alignment')
   aligned=whisperx.align(segments,am,meta,audio,'cpu',return_char_alignments=False)
   result['aligned_words']=aligned['word_segments'];result['alignment_status']='completed'
  except Exception as e:result['alignment_status']='blocked';result['alignment_error_type']=type(e).__name__
 results[slug]=result;print(slug,result['transcript'],result['normalized_word_error_rate'],flush=True)
 (OUT/f'{kind}.json').write_text(json.dumps({'tool':kind,'model':'small.en','device':'cpu','compute_type':'int8','expected':EXPECTED,'initial_prompt':None,'audio_decode':'FFmpeg mono 16kHz PCM; no denoising, gain change or replacement audio','notes':'WhisperX shares the faster-whisper backend and weights; agreement is not independent corroboration. ASR is an estimate, not ground-truth listening review. WER ignores punctuation/case, expands contractions to their full words, and treats 70 as seventy.','clips':results},indent=2)+'\n')
