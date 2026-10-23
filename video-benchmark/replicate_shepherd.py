#!/usr/bin/env python3
"""One Replicate provider comparison, isolated from the API Mart spending ledger."""
import argparse,hashlib,json,os,time,urllib.request,urllib.error,urllib.parse,sys
from pathlib import Path
from decimal import Decimal
import benchmark as b
ROOT=b.ROOT;ROUND='replicate_shepherd_round5';KEY=ROUND+'/landscape/pixverse';STATE=ROOT/'.runtime/replicate-state.json';CREDIT=Decimal('6.74')
class Client:
 def request(self,method,path,body=None):
  if not path.startswith('/v1/') or '://' in path:raise b.Blocked('Unexpected Replicate API route')
  data=json.dumps(body).encode() if body is not None else None
  req=urllib.request.Request('https://api.replicate.com'+path,data=data,method=method,headers={'Authorization':'Bearer '+os.environ['REPLICATE_API_TOKEN'],'Content-Type':'application/json','User-Agent':'CodexVideoBenchmark/1.0'})
  try:
   with urllib.request.build_opener(b.NoRedirect()).open(req,timeout=90) as r:return json.load(r)
  except urllib.error.HTTPError as e:raise b.Blocked(f'Replicate API HTTP {e.code}; details withheld') from None
  except (OSError,ValueError):raise b.Blocked('Replicate API request failed; response details withheld') from None

def state():
 if STATE.exists():return json.loads(STATE.read_text())
 p=ROOT/'results'/ROUND/'results.json'
 if p.exists():
  d=json.loads(p.read_text())
  if d.get('submitted_or_uncertain') or d.get('completed_jobs'):raise b.Blocked('Public Replicate results exist without private ledger; restore it, never regenerate')
 return {'provider':'Replicate','credit_snapshot_usd':'6.74','jobs':{}}
def save(s):b.atomic_json(STATE,s,private=True)
def config():return json.loads((ROOT/'config/replicate-shepherd-round5.json').read_text())
def payload(cfg,url):return {'input':{'prompt':cfg['prompt'],'image':url,'quality':'1080p','duration':15,'aspect_ratio':'16:9','generate_audio_switch':True,'generate_multi_clip_switch':False}}
def quote():
 p=ROOT/'results'/ROUND/'pricing.json'
 if not p.exists():raise b.Blocked('Official current fixed output price must be verified before a paid Replicate request')
 q=json.loads(p.read_text())
 if q.get('model_id')!='pixverse/pixverse-v6' or q.get('quality')!='1080p' or q.get('audio') is not True or q.get('billing_type')!='output_second' or not b.fresh(q['verified_at'],hours=1):raise b.Blocked('Missing/expired fixed audio-inclusive 1080p pricing evidence')
 price=b.money(q['usd_per_second']);estimate=price*15;bound=estimate*b.Decimal('1.25')
 if not 0<bound<=CREDIT:raise b.Blocked('Quote with 25% margin exceeds the user-reported Replicate credit')
 return q,estimate,bound

def reference_url(cfg):
 p=ROOT/cfg['reference'];digest=hashlib.sha256(p.read_bytes()).hexdigest()
 if digest!=cfg['reference_sha256']:raise b.Blocked('Reference bytes differ from the prior comparison')
 previous=b.read_state(ROOT).get('reference_uploads',{}).get(digest)
 if not previous or not b.fresh(previous['uploaded_at'],hours=70):raise b.Blocked('Original public reference URL expired; upload the exact same file before submitting')
 return b.valid_media_url(previous['url'])

def report(cfg,s):
 j=s['jobs'].get(KEY,{})
 public={k:v for k,v in j.items() if k not in {'prediction_id','output_url','request_sha256','private_prediction'}}
 d=dict(provider='Replicate',round_id=ROUND,generated_at=b.now(),completed_jobs=int(j.get('status')=='completed'),submitted_or_uncertain=int(bool(j)),job=public,model_id=cfg['model_id'],script=cfg['script'],prompt=cfg['prompt'],reference_file='../../'+cfg['reference'],reference_sha256=cfg['reference_sha256'],reference_provenance=cfg['reference_provenance'],comparison=cfg['comparison'],billing_note='Quoted fixed-output estimate is reported separately from an actual billed charge. Account credit was provided by the user, not read from a billing API.')
 b.atomic_json(ROOT/'results'/ROUND/'results.json',d);return d

def poll(client,cfg,s,j):
 if j['status'] in ['failed','submission_unknown']:return
 deadline=time.monotonic()+1800
 while True:
  d=client.request('GET','/v1/predictions/'+urllib.parse.quote(j['prediction_id'],safe=''))
  j['last_polled_at']=b.now();status=d.get('status');j['provider_status']=status
  if status in ['failed','canceled','aborted']:
   j.update(status='failed',reason='Provider task failed; no automatic paid retry');save(s);report(cfg,s);return
  if status=='succeeded':
   u=d.get('output')
   if not isinstance(u,str):raise b.Blocked('Unexpected output schema; reconcile original prediction')
   j.update(status='download_pending',output_url=b.valid_media_url(u),provider_metrics=d.get('metrics',{}),provider_version=d.get('version'),completed_at=d.get('completed_at'))
   duration=j['provider_metrics'].get('video_output_duration_seconds')
   if duration is not None:
    metered=b.money(duration)*(b.money(j['estimated_cost_usd'])/15);j['metered_cost_estimate_usd']=str(metered)
    if metered>b.money(j['authorized_usd']):
     j.update(status='billing_violation',reason='Metered estimate exceeds conservative reservation');save(s);report(cfg,s);raise b.Blocked(j['reason'])
   save(s);report(cfg,s)
   target=ROOT/'results'/ROUND/'landscape/pixverse.mp4'
   b.download(j['output_url'],target)
   j.update(status='completed',file=str(target.relative_to(ROOT/'results')),technical=b.analyze_video(target))
   save(s);report(cfg,s);return
  if status not in ['starting','processing']:raise b.Blocked('Unexpected provider status; original prediction retained, never resubmit')
  j['status']='pending';save(s)
  if time.monotonic()>deadline:raise b.Blocked('Polling timed out; resume existing prediction ID only')
  time.sleep(7)

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['dry-run','generate','resume','report']);a=p.parse_args();cfg=config()
 with b.locked(ROOT):
  s=state()
  if a.command in ['dry-run','generate'] and KEY not in s['jobs']:
   q,estimate,bound=quote();print('Verified estimated cost USD',estimate,'reserved with margin USD',bound,flush=True)
   if a.command=='generate':
    if any(j['status'] not in ['completed','failed'] for j in s['jobs'].values()):raise b.Blocked('Unresolved Replicate submission blocks new paid work')
    used=sum((b.money(j['authorized_usd']) for j in s['jobs'].values()),Decimal(0))
    if used+bound>CREDIT:raise b.Blocked('Replicate ledger exceeds authorized user credit')
    request=payload(cfg,reference_url(cfg));client=Client();client.request('GET','/v1/account')
    j=dict(key=KEY,status='submitting',submitted_at=b.now(),estimated_cost_usd=str(estimate),authorized_usd=str(bound),actual_billed_usd=None,model_id=cfg['model_id'],prompt_sha256=hashlib.sha256(cfg['prompt'].encode()).hexdigest(),reference_sha256=cfg['reference_sha256'],request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest())
    s['jobs'][KEY]=j;save(s);report(cfg,s)
    try:
     d=client.request('POST','/v1/models/pixverse/pixverse-v6/predictions',request);prediction=d.get('id')
     if not isinstance(prediction,str) or not prediction:raise b.Blocked('No usable prediction ID')
     j.update(prediction_id=prediction,status='pending');save(s)
    except Exception:
     j.update(status='submission_unknown',reason='Paid POST outcome uncertain; reconcile, never automatically repeat');save(s);report(cfg,s);raise b.Blocked(j['reason']) from None
    print('Submitted one Replicate job; prediction ID saved privately',flush=True)
  if a.command in ['generate','resume'] and KEY in s['jobs']:
   j=s['jobs'][KEY]
   if j['status'] in ['submitting','submission_unknown','billing_violation']:raise b.Blocked('Uncertain submission; no automatic new POST')
   if j['status'] not in ['completed','failed']:poll(Client(),cfg,s,j)
  d=report(cfg,s);print('Replicate status:',d['job'].get('status','planned'),flush=True)
if __name__=='__main__':
 try:main()
 except b.Blocked as e:print('BLOCKED:',e,file=sys.stderr);sys.exit(2)
