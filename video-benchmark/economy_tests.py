#!/usr/bin/env python3
"""Four six-second economy-model comparisons; shared durable spending ledger."""
import argparse, hashlib, json, os, sys, time, urllib.request, zipfile
from pathlib import Path
import benchmark as b
import reference_tests as ref
ROUND = 'economy_round3'
ROUND_CAP = b.Decimal('1.38')
GLOBAL_CAP = b.Decimal('12')
MODELS = {'wan_flash': 'wan2.6-i2v-flash', 'pixverse': 'pixverse-v6'}

def round_used(state):
    return sum((b.money(j['authorized_usd']) for k,j in state['jobs'].items() if k.startswith(ROUND+'/')),b.Decimal(0))

def ensure(state, amount, available=None):
    if round_used(state)+amount > ROUND_CAP or b.used_budget(state)+amount > GLOBAL_CAP:
        raise b.Blocked('Economy round or existing global spending authorization exceeded')
    if available is not None and amount > b.money(available):
        raise b.Blocked('Insufficient available balance for conservative plan')

def prices(cfg):
    quotes={}
    if not b.fresh(cfg['documentation_verified_at']):raise b.Blocked('Refresh official parameter documentation before paid work')
    for slug,spec in cfg['models'].items():
        if MODELS.get(slug)!=spec['model_id']: raise b.Blocked('Unexpected model')
        url='https://api.apimart.ai/api/pricing/model?model='+spec['model_id']
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CodexVideoBenchmark/1.0'}),timeout=30) as r:
            result=json.load(r)
        d=result['data']
        if result.get('success') is not True or d.get('model_name')!=spec['model_id'] or d.get('billing_type')!='per_second':
            raise b.Blocked('Unverified fixed-second audio price')
        listed=b.money(d['billing_tiers']['720P-audio'])
        paid=b.money(d['billing_tier_paid_prices']['720P-audio'])
        if not 0 < paid <= listed: raise b.Blocked('Unexpected rate')
        quotes[slug]={'estimate_usd':str(paid*6),'maximum_charge_usd':str(listed*6),
            'maximum_reservation_usd':str(listed*6),'price_checked_at':b.now(),'pricing_source':url,
            'pricing_basis':'Six seconds at 720p audio-inclusive tier; one first-frame still, no reference video/audio. Undiscounted rate plus 25% reserved.'}
    return quotes

def jobs(cfg,quotes):
    return [dict(key=f'{ROUND}/{layout}/{slug}',round=ROUND,layout=layout,test=layout,slug=slug,
        model_id=spec['model_id'],name=spec['name'],resolution='720p',prompt=scene['prompt'],
        reference_file=scene['reference'],status='planned',**quotes[slug])
        for layout,scene in cfg['layouts'].items() for slug,spec in cfg['models'].items()]

def payload(job,image_url):
    if MODELS.get(job['slug'])!=job['model_id']:raise b.Blocked('Unexpected model')
    request=dict(model=job['model_id'],prompt=job['prompt'],duration=6,resolution='720p',
        image_urls=[image_url],audio=True,watermark=False)
    if job['slug']=='wan_flash':request.update(prompt_extend=False)
    else:request.update(motion_mode='normal',generate_multi_clip_switch=False)
    return request

def execute(cfg, quotes, api, root=b.ROOT, resume=False):
    if not os.environ.get('APIMART_API_KEY'):
        raise b.Blocked('Existing API Mart binding is not injected; no paid generation')
    state = b.read_state(root)
    client = b.Client(os.environ['APIMART_API_KEY'])
    available = b.account_check(client, api, state, root)
    for old in state['jobs'].values():
        if old['status'] in {'submitting', 'submission_unknown', 'billing_violation'}:
            raise b.Blocked('Uncertain submission or prior billing violation blocks all new work')
        if old.get('task_id') and old['status'] not in {'completed', 'failed'}:
            ref.poll_allow_cdn_deferral(client, api, old, root, state)
            available = b.account_check(client, api, state, root)
    if any(j['status'] == 'billing_violation' for j in state['jobs'].values()):
        raise b.Blocked('A completed charge exceeded its bound; no new jobs')
    if resume:
        return
    remaining = [j for j in jobs(cfg, quotes) if j['key'] not in state['jobs']]
    total = sum((b.charge_bound(j) for j in remaining), b.Decimal(0))
    ensure(state, total, available)
    state.setdefault('round_plans', {}).setdefault(ROUND, {
        'authorized_at': b.now(), 'round_limit_usd': '1.38', 'global_limit_usd': '12',
        'source': 'User requested both economy models, two six-second scenes; uses remaining existing $12 authorization'})
    b.save_state(root, state)
    urls = {layout: ref.upload(root, state, scene) for layout, scene in cfg['layouts'].items()
            if any(j['layout'] == layout for j in remaining)}
    for job in remaining:
        if not b.fresh(job['price_checked_at'], hours=1):
            raise b.Blocked('Quote expired; refresh prices before another paid job')
        available = b.account_check(client, api, state, root)
        bound = b.charge_bound(job)
        ensure(state, bound, available)
        request = payload(job, urls[job['layout']])
        job.update(status='submitting', authorized_usd=str(bound), submitted_at=b.now(),
            submitted_epoch=time.time(), actual_cost_usd=None,
            request_sha256=hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
        state['jobs'][job['key']] = job
        b.save_state(root, state)
        try:
            response = client.request('POST', api['generation_path'], request)
            task_id = b.pointer(response, api['submission_task_id_pointer'])
            if not isinstance(task_id, str) or not task_id.strip():
                raise b.Blocked('No usable task ID returned')
            job.update(task_id=task_id, status='pending')
            b.save_state(root, state)
        except Exception:
            job.update(status='submission_unknown', reason='Paid POST outcome uncertain; reconcile, never automatically resubmit')
            b.save_state(root, state)
            raise b.Blocked(job['reason']) from None
        print('Submitted:', job['key'], 'task:', task_id, 'authorization USD:', bound, flush=True)
        after_submit = b.account_check(client, api, state, root)
        decrease = max(b.Decimal(0), b.money(available) - b.money(after_submit))
        job['observed_balance_decrease_after_submit_usd'] = str(decrease)
        b.save_state(root, state)
        ref.poll_allow_cdn_deferral(client, api, job, root, state)
        b.account_check(client, api, state, root)
        report(cfg, quotes, root)
        print('Finished:', job['key'], job['status'], 'billed USD:', job.get('actual_cost_usd'), flush=True)
        if job['status'] == 'billing_violation' or decrease > bound:
            raise b.Blocked('Unexpected charge or reservation; all remaining new paid jobs stopped')


def report(cfg,quotes,root=b.ROOT):
    state=b.read_state(root); folder=root/'results'/ROUND;folder.mkdir(parents=True,exist_ok=True)
    rows=[]
    for job in jobs(cfg,quotes):
        old=state['jobs'].get(job['key'],job)
        row={k:v for k,v in old.items() if k not in {'task_id','result_url','request_sha256'}}
        row.update(key=('speech' if job['layout']=='speech' else 'music')+'/'+job['slug'],test='speech' if job['layout']=='speech' else 'music',
            reference_file='../../'+job['reference_file'],scores=dict.fromkeys(b.WEIGHTS),
            duration_note='Six requested seconds; native 720p vertical output and native model-generated audio.')
        if row.get('file'):row['file']=str(Path(row['file']).relative_to(ROUND))
        rows.append(row)
    billed=sum((b.money(j['actual_cost_usd']) for j in rows if j.get('actual_cost_usd') is not None),b.Decimal(0))
    data=dict(generated_at=b.now(),round_id=ROUND,requested_jobs=4,completed_jobs=sum(j['status']=='completed' for j in rows),
        submitted_or_uncertain=sum(j['status']!='planned' for j in rows),known_actual_cost_usd=str(billed),
        conservative_committed_usd=str(round_used(state)),authorized_limit_usd=str(ROUND_CAP),actual_cost_complete=all(j.get('actual_cost_usd') is not None for j in rows),
        remaining_balance_usd=state['account_checks'][-1]['available_usd'] if state['account_checks'] else None,
        rubric_weights=b.WEIGHTS,blockers=[],jobs=rows,
        quality_assessment='Audio presence and technical metrics measured; exact speech, lip synchronization and naturalness require playback review.')
    validation=folder/'validation.json'
    if validation.exists():data['validation']=json.loads(validation.read_text())
    b.atomic_json(folder/'results.json',data);b.atomic_json(folder/'pricing.json',quotes)
    b.write_csv(folder/'costs.csv',rows,['layout','model_id','status','estimate_usd','authorized_usd','actual_cost_usd'])
    b.write_csv(folder/'technical_metrics.csv',[dict(layout=j['layout'],model_id=j['model_id'],**j.get('technical',{})) for j in rows],
        ['layout','model_id','duration_seconds','width','height','frame_rate','audio_present','audio_codec','mean_volume_db','silence_percentage'])
    for csv_path in folder.glob('*.csv'):csv_path.write_text(csv_path.read_text())
    template=(root/'templates/comparison.html').read_text().replace('AI video quality benchmark','Economy video models: grandmother and wildlife')
    template=template.replace('Four models · two shared prompts · native audio · portrait video','Two models · six-second clips · fresh reference images · native audio')
    template=template.replace('>Speech</button>','>Grandmother</button>').replace('>Music</button>','>River otters</button>')
    template=template.replace('Music / 10','Wildlife / 10').replace("data.completed_jobs+'/8 real videos completed.","data.completed_jobs+'/4 real videos completed.")
    template=template.replace('apimart-video-benchmark-scores-v1','apimart-economy-round3-scores-v1')
    template=template.replace('The music test requires three landings with distinct synchronized footsteps and marimba notes.','The wildlife test requires two consistent otters, plausible movement, stream ambience and synchronized splashes. The grandmother and her life story are fictional.')
    (folder/'comparison.html').write_text(template.replace('__BENCHMARK_DATA__',json.dumps(data).replace('<','\u003c')))
    lines=['# Economy models: six-second reference tests','',f'Completed {data["completed_jobs"]}/4. Actual billed USD: {billed}. Latest available USD: {data["remaining_balance_usd"]}.',
        '', 'Both models receive the same fresh reference and detailed prompt for each scene. Native 720p vertical outputs with model-generated audio; no TTS or replacement soundtrack. The grandmother and her recollection are fictional.',
        '', '| Scene | Model | Status | Billed USD |','|---|---|---|---|']
    lines += [f'| {j["layout"]} | {j["model_id"]} | {j["status"]} | {j.get("actual_cost_usd","pending")} |' for j in rows]
    lines += ['',data['quality_assessment'],'','Extract the whole archive and open comparison.html. Full prompts and references are included. No paid retries. Resume only existing task IDs with `python3 economy_tests.py resume`. Uses existing global $12 authorization, with a $1.38 conservative round cap.']
    (folder/'report.md').write_text('\n'.join(lines)+'\n')
    return data

def package(root=b.ROOT):
    target=root.parent/'economy-round3-results.zip'
    files=[p for p in (root/'results'/ROUND).rglob('*') if p.is_file()]
    files += list((root/'tests').glob('*.py'))
    files += list((root/'config').glob('*.json'))
    files += [root/'shorts_tests.py']
    files += [root/p for p in ['benchmark.py','reference_tests.py','economy_tests.py','templates/comparison.html','config/economy-round3.json','references/round3-otters.png','references/round3-grandmother.png']]
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.md','Extract all files and open video-benchmark/results/economy_round3/comparison.html. Four six-second native-audio vertical tests. Grandmother and story are fictional. Private spending ledger omitted; live CLI requires original environment state.')
        for p in sorted(set(files)):z.write(p,Path('video-benchmark')/p.relative_to(root))
    return target

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['dry-run','execute','resume','report','package']);args=parser.parse_args()
    cfg=json.loads((b.ROOT/'config/economy-round3.json').read_text());api=b.load()[0]['api']
    with b.locked(b.ROOT):
        qp=b.ROOT/'results'/ROUND/'pricing.json';quotes=json.loads(qp.read_text()) if qp.exists() else {}
        if args.command in {'dry-run','execute'}:
            quotes=prices(cfg);remaining=[j for j in jobs(cfg,quotes) if j['key'] not in b.read_state(b.ROOT)['jobs']]
            total=sum((b.charge_bound(j) for j in remaining),b.Decimal(0));ensure(b.read_state(b.ROOT),total)
            print('Remaining estimate USD',sum((b.money(j['estimate_usd']) for j in remaining),b.Decimal(0)),'conservative USD',total,flush=True)
        if args.command in {'execute','resume'}:
            execute(cfg,quotes,api,resume=args.command=='resume')
            state=b.read_state(b.ROOT)
            for key,j in state['jobs'].items():
                if key.startswith(ROUND+'/') and j.get('file'):j['technical']=b.analyze_video(b.ROOT/'results'/j['file'])
            b.save_state(b.ROOT,state)
        data=report(cfg,quotes);print('Completed',data['completed_jobs'],'/4; billed USD',data['known_actual_cost_usd'],flush=True)
        if args.command=='package':print(package())
if __name__=='__main__':
    try:main()
    except b.Blocked as e:print('BLOCKED:',e,file=sys.stderr);sys.exit(2)
