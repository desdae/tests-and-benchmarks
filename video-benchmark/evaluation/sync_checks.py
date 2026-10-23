"""Official SyncNet CPU pipeline plus a known 200 ms audio-delay control."""
import os,subprocess,json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TOOLS=Path('/workspace/video-eval-tools');OUT=ROOT/'results/economy_round3/evaluation';WORK=TOOLS/'sync-work';REPO=TOOLS/'syncnet';PY='/workspace/video-eval-venv/bin/python'
ENV=dict(os.environ,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
def run(args,name):
 p=subprocess.run(args,cwd=REPO,env=ENV,text=True,capture_output=True,check=True,timeout=600)
 log=p.stdout+p.stderr;(OUT/(name+'.log')).write_text(log);return log
def parse(log):
 return {'offset_frames_25fps':int(re.search(r'AV offset:\s*(-?\d+)',log)[1]),'minimum_distance':float(re.search(r'Min dist:\s*([\d.]+)',log)[1]),'confidence':float(re.search(r'Confidence:\s*([\d.]+)',log)[1])}
clips={}
for slug in ['wan_flash','pixverse']:
 crop=WORK/'pycrop'/slug/'00000.avi'
 if not crop.exists():run([PY,'run_pipeline.py','--videofile',str(ROOT/'results/economy_round3/speech'/f'{slug}.mp4'),'--reference',slug,'--data_dir',str(WORK)],slug+'-face-pipeline')
 tracks=list(crop.parent.glob('0*.avi'))
 if len(tracks)!=1:raise RuntimeError('Expected exactly one face track; review tracking before interpreting scores')
 log=run([PY,'run_syncnet.py','--initial_model',str(TOOLS/'weights/syncnet_v2.model'),'--reference',slug,'--data_dir',str(WORK),'--batch_size','8'],slug+'-syncnet')
 result=parse(log);result['estimated_audio_delay_ms']=-40*result['offset_frames_25fps'];result['tracks']=len(tracks);clips[slug]=result
control=WORK/'wan-delayed200.avi'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(WORK/'pycrop/wan_flash/00000.avi'),'-map','0:v:0','-map','0:a:0','-c:v','copy','-af','adelay=200:all=1','-t','6','-c:a','pcm_s16le',str(control)],check=True)
log=run([PY,'demo_syncnet.py','--initial_model',str(TOOLS/'weights/syncnet_v2.model'),'--videofile',str(control),'--tmp_dir',str(TOOLS/'sync-control'),'--reference','delayed200','--batch_size','8'],'syncnet-delay-control')
ctrl=parse(log);delta=ctrl['offset_frames_25fps']-clips['wan_flash']['offset_frames_25fps'];ctrl.update(injected_audio_delay_ms=200,observed_offset_change_frames=delta,passed=delta==-5)
if not ctrl['passed']:raise RuntimeError('Known audio-delay control failed; scores must not be treated as verified')
data={'tool':'SyncNet','device':'cpu','fps_for_evaluation':25,'clips':clips,'control':ctrl,
 'method':'Official S3FD face detection/tracking, official 224x224 crops and MFCC preprocessing, official SyncNet V2 weights; original MP4s unchanged.',
 'interpretation':'Positive estimated audio delay means speech is later than video. 40 ms temporal granularity. Confidence is median distance minus minimum distance, not a probability or a percentage. Minimum distance is measured at the best searched offset, not necessarily zero lag. One short clip per model cannot establish a model ranking.',
 'weight_sha256':hashlib.sha256((TOOLS/'weights/syncnet_v2.model').read_bytes()).hexdigest()}
(OUT/'syncnet.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
