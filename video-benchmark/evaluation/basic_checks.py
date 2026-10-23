"""CPU-only decoded-frame checks, with explicit heuristic thresholds."""
import cv2,numpy as np,json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/economy_round3/evaluation';OUT.mkdir(exist_ok=True)
results={}
for slug in ['wan_flash','pixverse']:
 p=ROOT/'results/economy_round3/speech'/f'{slug}.mp4'
 cap=cv2.VideoCapture(str(p));fps=cap.get(cv2.CAP_PROP_FPS);prev=None;diff=[];blur=[];black=[];levels=[]
 while True:
  ok,frame=cap.read()
  if not ok:break
  gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
  blur.append(float(cv2.Laplacian(gray,cv2.CV_64F).var()));levels.append(float(gray.mean()))
  black.append(float(np.mean(gray<16))>.98)
  if prev is not None:diff.append(float(cv2.absdiff(gray,prev).mean()))
  prev=gray
 cap.release()
 def longest(flags):
  n=best=0
  for x in flags:n=n+1 if x else 0;best=max(best,n)
  return best/fps
 cmd=['ffmpeg','-hide_banner','-nostats','-i',str(p),'-vf','blackdetect=d=0.1:pix_th=0.10,freezedetect=n=-50dB:d=0.5','-af','volumedetect','-f','null','-']
 proc=subprocess.run(cmd,text=True,capture_output=True,check=True);(OUT/f'{slug}-ffmpeg.log').write_text(proc.stderr)
 results[slug]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frames_decoded':len(blur),'fps':fps,'opencv':{
  'black_frame_count_98pct_pixels_below_16':sum(black),'longest_exact_duplicate_frame_run_seconds':longest(np.array(diff)==0),
  'consecutive_gray_mean_abs_difference_mean':float(np.mean(diff)),'laplacian_variance_median':float(np.median(blur)),
  'brightness_mean':float(np.mean(levels))},'ffmpeg_black_or_freeze_events':[l.strip() for l in proc.stderr.splitlines() if 'black_start:' in l or 'freeze_start:' in l or 'freeze_duration:' in l]}
(OUT/'basic.json').write_text(json.dumps({'notes':'Heuristics only: low frame change can be valid stillness; Laplacian variance is not an overall quality score. No reference-quality ground truth.','clips':results},indent=2)+'\n')
print(json.dumps(results,indent=2))
