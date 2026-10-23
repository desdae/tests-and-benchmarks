"""Run published CPU-compatible visual metrics with official trained weights."""
import os
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
import sys,json,time,random,hashlib
from pathlib import Path
import torch,numpy as np,yaml
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/economy_round3/evaluation';TOOLS=Path('/workspace/video-eval-tools')
torch.set_num_threads(4);torch.set_num_interop_threads(1)
kind=sys.argv[1];random.seed(42);np.random.seed(42);torch.manual_seed(42)
results={}
if kind=='dover':
 from dover.datasets import UnifiedFrameSampler,spatial_temporal_view_decomposition
 import dover.models.evaluator as ev
 original=ev.convnext_3d_tiny
 # Complete DOVER checkpoint is loaded strictly below, replacing all backbone tensors.
 # Skip a redundant ImageNet initialization download; no learned tensors left random.
 ev.convnext_3d_tiny=lambda **kw:original(pretrained=False)
 cfg=yaml.safe_load((TOOLS/'DOVER/dover.yml').read_text());model=ev.DOVER(**cfg['model']['args']).cpu()
 weight=TOOLS/'weights/DOVER.pth';model.load_state_dict(torch.load(weight,map_location='cpu',weights_only=True),strict=True)
 dopt=cfg['data']['val-l1080p']['args'];samplers={}
 for k,s in dopt['sample_types'].items():
  samplers[k]=UnifiedFrameSampler(s['clip_len'],s['num_clips'],s['frame_interval']) if 't_frag' not in s else UnifiedFrameSampler(s['clip_len']//s['t_frag'],s['t_frag'],s['frame_interval'],s['num_clips'])
elif kind=='fastvqa':
 from fastvqa.datasets import get_spatial_fragments,SampleFrames
 from fastvqa.models import DiViDeAddEvaluator
 import decord
 decord.bridge.set_bridge('torch')
 cfg=yaml.safe_load((TOOLS/'FAST-VQA/options/fast/fast-b.yml').read_text());model=DiViDeAddEvaluator(**cfg['model']['args']).cpu()
 weight=TOOLS/'weights/FAST_VQA_B_1_4.pth';model.load_state_dict(torch.load(weight,map_location='cpu',weights_only=False)['state_dict'],strict=True)
else:
 sys.path.insert(0,str(TOOLS/'VBench'))
 from vbench.temporal_flickering import cal_score
 weight=None
mean=torch.tensor([123.675,116.28,103.53]);std=torch.tensor([58.395,57.12,57.375])
slugs=['wan_flash','pixverse']+(['wan_blurred_control'] if '--negative-control' in sys.argv else [])
for slug in slugs:
 random.seed(42);np.random.seed(42);torch.manual_seed(42);start=time.monotonic();p=(TOOLS/'quality-control.mp4') if slug=='wan_blurred_control' else ROOT/'results/economy_round3/speech'/f'{slug}.mp4'
 if kind=='dover':
  views,_=spatial_temporal_view_decomposition(str(p),dopt['sample_types'],samplers)
  for k,v in views.items():
   n=dopt['sample_types'][k].get('num_clips',1)
   views[k]=((v.permute(1,2,3,0)-mean)/std).permute(3,0,1,2).reshape(v.shape[0],n,-1,*v.shape[2:]).transpose(0,1)
  with torch.inference_mode():raw=[r.mean().item() for r in model(views)]
  # Official evaluate_one_video.py fused-score calibration.
  z=(raw[0]-.1107)/.07355*.6104+(raw[1]+.08285)/.03774*.3896
  result={'raw_branch_scores':raw,'branch_order':list(views),'normalized_fused_score':float(1/(1+np.exp(-z)))}
 elif kind=='fastvqa':
  reader=decord.VideoReader(str(p),num_threads=2);samples={}
  for k,s in cfg['data']['val-kv1k']['args']['sample_types'].items():
   indices=SampleFrames(clip_len=s['clip_len'],num_clips=s['num_clips'])(len(reader))
   video=reader.get_batch(indices).permute(3,0,1,2)
   v=get_spatial_fragments(video,**s);v=((v.permute(1,2,3,0)-mean)/std).permute(3,0,1,2)
   samples[k]=v.reshape(v.shape[0],s['num_clips'],-1,*v.shape[2:]).transpose(0,1)
  with torch.inference_mode():raw=model(samples).mean().item()
  result={'raw_score':raw,'normalized_score':float(1/(1+np.exp(-(raw-(-.110198185))/.04178565)))}
 else:result={'temporal_flickering_score':float(cal_score(str(p))),'caveat':'Official metric assumes static video. Speaking motion and camera movement confound the score; this is not a full VBench evaluation.'}
 result['elapsed_seconds']=round(time.monotonic()-start,3);results[slug]=result;print(slug,json.dumps(result),flush=True)
 data={'tool':kind,'device':'cpu','seed':42,'clips':results,'weight_sha256':hashlib.sha256(weight.read_bytes()).hexdigest() if weight else None,
 'interpretation':'Higher normalized score is better under the published calibration, not a probability of correctness or a calibrated human rating. Visual only; cannot measure speech or lip sync.'}
 (OUT/(kind+('-controls' if '--negative-control' in sys.argv else '')+'.json')).write_text(json.dumps(data,indent=2)+'\n')
