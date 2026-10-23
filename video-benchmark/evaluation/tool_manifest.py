"""Record tested sources, licenses, versions and environment without credentials."""
from pathlib import Path
import subprocess,json,importlib.metadata as md,hashlib,platform,os
ROOT=Path(__file__).resolve().parents[1];TOOLS=Path('/workspace/video-eval-tools')
repos={}
for name in ['syncnet','DOVER','FAST-VQA','VBench','silero-vad']:
 p=TOOLS/name
 repos[name]={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip(),
 'url':subprocess.check_output(['git','config','--get','remote.origin.url'],cwd=p,text=True).strip(),
 'license_note': 'S-Lab non-commercial license; commercial use requires contacting contributors' if name in ['DOVER','FAST-VQA'] else 'MIT' if name in ['syncnet','silero-vad'] else 'Apache-2.0; component weights may have separate terms'}
versions={}
for name in ['torch','torchvision','torchaudio','opencv-python','faster-whisper','whisperx','transformers','numpy','decord','dover','fastvqa']:
 try:versions[name]=md.version(name)
 except md.PackageNotFoundError:versions[name]=None
weights={p.name:{'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (TOOLS/'weights').glob('*') if p.is_file()}
asr_cache=TOOLS/'weights/models--Systran--faster-whisper-small.en'
refs=(asr_cache/'refs/main').read_text().strip()
for p in (asr_cache/'snapshots'/refs).glob('*'):
 if p.is_file():weights['faster-whisper-small.en/'+p.name]={'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for p in (TOOLS/'weights/alignment').glob('*.pth'):
 weights['alignment/'+p.name]={'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
data={'asr_model_revision':refs,'python':platform.python_version(),'platform':platform.platform(),'hardware':{'cpu_visible':len(os.sched_getaffinity(0)),'cpu_quota':'4 cores','memory_limit_gib':32,'gpu':False},'versions':versions,'repositories':repos,'weights':weights,'compatibility_notes':[
'DOVER declares torch~=1.13, unavailable as a Python 3.12 wheel. Tested here with CPU torch 2.8.0; all trained checkpoint tensors loaded strictly, inference completed. This is a compatibility-tested adaptation, not the authors pinned training environment.',
'FAST-VQA declares old clip and sk-video distribution names; openai-clip and scikit-video provide the actual required modules.',
'VBench setup.py requires CUDA. Its official temporal_flickering module was imported and executed from pinned source on CPU; the full CUDA package and full benchmark were not run.',
'DOVER random ImageNet initialization download skipped because the complete official DOVER checkpoint strictly replaces all model tensors. Model architecture and scoring calibration unchanged.',
'No API Mart calls, hosted evaluation API charges, uploaded videos or paid GPU services used.']}
(ROOT/'results/economy_round3/evaluation/environment.json').write_text(json.dumps(data,indent=2)+'\n');print('Environment manifest saved')
