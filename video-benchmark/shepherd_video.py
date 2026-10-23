#!/usr/bin/env python3
"""One 15-second PixVerse shepherd clip, with durable shared spending protection."""
import argparse,hashlib,json,os,time,urllib.request,sys
from pathlib import Path
import benchmark as b
import reference_tests as ref
ROOT=b.ROOT;ROUND='shepherd_round4';KEY=ROUND+'/landscape/pixverse';GLOBAL=b.Decimal('12');CAP=b.Decimal('1.875')

def settings():return json.loads((ROOT/'config/shepherd-round4.json').read_text())
def ensure(state,bound,balance):
 if b.used_budget(state)+bound>GLOBAL or bound>CAP or bound>b.money(balance):raise b.Blocked('Verified conservative price exceeds existing shared authorization or available balance')
def pricing():
 url='https://api.apimart.ai/api/pricing/model?model=pixverse-v6'
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CodexVideoBenchmark/1.0'}),timeout=30) as r:d=json.load(r)
 p=d['data']
 if d.get('success') is not True or p.get('model_name')!='pixverse-v6' or p.get('billing_type')!='per_second':raise b.Blocked('Unverified fixed-per-second model pricing')
 paid=b.money(p['billing_tier_paid_prices']['1080P-audio']);listed=b.money(p['billing_tiers']['1080P-audio'])
 if not 0<paid<=listed:raise b.Blocked('Unexpected audio-inclusive tier')
 return dict(estimate_usd=str(paid*15),maximum_charge_usd=str(listed*15),maximum_reservation_usd=str(listed*15),price_checked_at=b.now(),pricing_source=url,pricing_basis='15 requested seconds, 1080p audio-inclusive tier, one adapted first-frame still; undiscounted list price plus 25% safety margin reserved.')
def payload(cfg,url):
 return dict(model='pixverse-v6',prompt=cfg['prompt'],duration=15,resolution='1080p',image_urls=[url],audio=True,watermark=False,motion_mode='normal',generate_multi_clip_switch=False)
def report(cfg,state):
 old=state['jobs'].get(KEY,{});public={k:v for k,v in old.items() if k not in {'task_id','result_url','request_sha256'}}
 data=dict(round_id=ROUND,generated_at=b.now(),completed_jobs=int(old.get('status')=='completed'),submitted_or_uncertain=int(bool(old)),job=public,script=cfg['script'],prompt=cfg['prompt'],reference_provenance=cfg['reference_provenance'],reference_file='../../'+cfg['reference'],known_actual_cost_usd=old.get('actual_cost_usd'),remaining_balance_usd=state['account_checks'][-1]['available_usd'] if state['account_checks'] else None)
 b.atomic_json(ROOT/'results'/ROUND/'results.json',data);return data

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['dry-run','generate','resume','report']);args=p.parse_args();cfg=settings();api=b.load()[0]['api']
 with b.locked(ROOT):
  state=b.read_state(ROOT)
  if args.command in ['dry-run','generate'] and KEY not in state['jobs']:
   q=pricing();bound=b.charge_bound(q);print('Estimated USD',q['estimate_usd'],'conservative authorization USD',bound,flush=True)
   if not b.fresh(cfg['documentation_verified_at']):raise b.Blocked('Refresh model parameter documentation')
   if args.command=='generate':
    client=b.Client(os.environ['APIMART_API_KEY']);balance=b.account_check(client,api,state,ROOT)
    for old in state['jobs'].values():
     if old['status'] in {'submitting','submission_unknown','billing_violation'} or (old.get('task_id') and old['status'] not in {'completed','failed'}):raise b.Blocked('Unresolved prior task blocks a new paid submission')
    ensure(state,bound,balance);url=ref.upload(ROOT,state,cfg);request=payload(cfg,url)
    job=dict(key=KEY,round=ROUND,slug='pixverse',model_id='pixverse-v6',name='PixVerse V6',status='submitting',prompt=cfg['prompt'],target_duration_seconds=15,target_resolution='1080p',aspect_ratio='16:9',native_audio_required=True,reference_file=cfg['reference'],authorized_usd=str(bound),submitted_at=b.now(),submitted_epoch=time.time(),actual_cost_usd=None,request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),**q)
    state['jobs'][KEY]=job;state.setdefault('round_plans',{})[ROUND]=dict(round_cap_usd=str(CAP),global_cap_usd=str(GLOBAL),source='User requested one 15-second landscape PixVerse shepherd test with word-highlighted captions')
    b.save_state(ROOT,state);report(cfg,state)
    try:
     response=client.request('POST',api['generation_path'],request);task=b.pointer(response,api['submission_task_id_pointer'])
     if not isinstance(task,str) or not task.strip():raise b.Blocked('No usable task ID')
     job.update(task_id=task,status='pending');b.save_state(ROOT,state)
    except Exception:
     job.update(status='submission_unknown',reason='Paid POST outcome uncertain; reconcile, never automatically resubmit');b.save_state(ROOT,state);report(cfg,state);raise b.Blocked(job['reason']) from None
    print('Submitted one PixVerse job; durable task ID saved privately',flush=True)
    after=b.account_check(client,api,state,ROOT)
    if max(b.Decimal(0),b.money(balance)-b.money(after))>bound:raise b.Blocked('Unexpected provider reservation; stop')
  if args.command in ['generate','resume'] and KEY in state['jobs']:
   job=state['jobs'][KEY]
   if job['status'] in {'submitting','submission_unknown','billing_violation'}:raise b.Blocked('Uncertain/violating task cannot be resubmitted')
   client=b.Client(os.environ['APIMART_API_KEY'])
   if job['status'] not in {'completed','failed'}:ref.poll_allow_cdn_deferral(client,api,job,ROOT,state)
   b.account_check(client,api,state,ROOT)
   if job.get('file'):job['technical']=b.analyze_video(ROOT/'results'/job['file']);b.save_state(ROOT,state)
  r=report(cfg,state);print('Status',r['job'].get('status','planned'),'actual USD',r['known_actual_cost_usd'],flush=True)
if __name__=='__main__':
 try:main()
 except b.Blocked as e:print('BLOCKED:',e,file=sys.stderr);sys.exit(2)
