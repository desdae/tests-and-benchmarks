#!/usr/bin/env python3
"""Small image-guided pilot sharing the original benchmark's $6 ledger."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import benchmark as b

ROOT = b.ROOT
SELECTED = {'wan3': ('wan3.0-video', '720P'), 'minimax_h3': ('MiniMax-H3', '768P')}


def settings(root=ROOT):
    return json.loads((root / 'config/reference-tests.json').read_text())


def get_prices():
    prices = {}
    for slug, (model_id, resolution) in SELECTED.items():
        url = 'https://api.apimart.ai/api/pricing/model?' + urllib.parse.urlencode({'model': model_id})
        request = urllib.request.Request(url, headers={'User-Agent': 'CodexVideoBenchmark/1.0', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise b.Blocked('Could not verify current public model pricing; no generation submitted') from None
        data = result.get('data', {})
        if result.get('success') is not True or data.get('model_name') != model_id or data.get('billing_type') != 'per_second':
            raise b.Blocked('Model pricing no longer matches the verified fixed-per-second contract')
        listed = b.money(data['resolution_prices'][resolution])
        payable = b.money(data['resolution_paid_prices'][resolution])
        if listed <= 0 or payable <= 0 or payable > listed:
            raise b.Blocked('Unexpected pricing multiplier; do not guess account charges')
        if slug == 'minimax_h3' and not (data.get('input_image_first_free') is True and data.get('input_image_free_count', 0) >= 1):
            raise b.Blocked('One input image is no longer in the documented free-image allowance')
        prices[slug] = {'model_id': model_id, 'resolution': resolution,
                        'estimate_usd': str(payable * 5), 'maximum_charge_usd': str(listed * 5),
                        'maximum_reservation_usd': str(listed * 5), 'checked_at': b.now(),
                        'source': url,
                        'basis': 'Fixed 5 requested seconds, explicit resolution, one still image, no video/audio references. '
                                 'Higher undiscounted list rate used for authorization; native audio included. '
                                 'Reservation estimate uses the same fixed-price quote; immediate balance check detects unexpected holds. '
                                 'This is a conservative client estimate, not a provider-enforced cap.'}
    return prices


def jobs_for(config, pilot, prices):
    if pilot['selected_models'] != list(SELECTED) or b.money(pilot['budget_usd']) != b.LIMIT:
        raise b.Blocked('Pilot is restricted to Wan3/MiniMax H3 and the existing $6 budget')
    if not b.fresh(pilot.get('documentation_verified_at')):
        raise b.Blocked('Refresh official image-to-video parameter and billing evidence before paid requests')
    models = {m['slug']: m for m in config['models']}
    jobs = []
    for test, spec in pilot['tests'].items():
        for slug in pilot['selected_models']:
            model = models[slug]
            quote = prices[slug]
            if model['model_id'] != SELECTED[slug][0]:
                raise b.Blocked('Model substitution prohibited')
            jobs.append({'key': f'reference/{test}/{slug}', 'test': test, 'slug': slug,
                'name': model['name'], 'model_id': model['model_id'], 'status': 'planned',
                'prompt': spec['prompt'], 'reference_file': spec['reference'],
                'target_duration_seconds': 5, 'target_resolution': quote['resolution'],
                'mode': 'image-to-video; first-frame reference', 'native_audio_required': True,
                'duration_note': 'Fixed 5 seconds; opening-frame reference supplied',
                'scores': dict.fromkeys(b.WEIGHTS), **quote})
    if len(jobs) != 4:
        raise b.Blocked('Exactly two tests on two selected models are permitted')
    return jobs


def upload(root, state, spec):
    path = root / spec['reference']
    if path.suffix != '.png' or not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise b.Blocked('Reference must be an existing PNG under the documented 20 MB upload limit')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    uploads = state.setdefault('reference_uploads', {})
    previous = uploads.get(digest)
    if previous and b.fresh(previous['uploaded_at'], hours=70):
        return previous['url']
    boundary = '----Benchmark' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    request = urllib.request.Request('https://api.apimart.ai/v1/uploads/images', data=body,
        headers={'Authorization': 'Bearer ' + os.environ['APIMART_API_KEY'],
                 'Content-Type': 'multipart/form-data; boundary=' + boundary,
                 'Accept': 'application/json', 'User-Agent': 'CodexVideoBenchmark/1.0'}, method='POST')
    try:
        with urllib.request.build_opener(b.NoRedirect()).open(request, timeout=90) as response:
            result = json.load(response)
        url = b.valid_media_url(result['url'])
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
        raise b.Blocked('Reference upload failed; response details withheld; no automatic upload retry') from None
    uploads[digest] = {'url': url, 'uploaded_at': b.now(), 'local_file': spec['reference'], 'sha256': digest}
    b.save_state(root, state)
    return url


def payload(job, image_url):
    common = {'model': job['model_id'], 'prompt': job['prompt'], 'duration': 5,
              'resolution': job['resolution'], 'watermark': False}
    if job['slug'] == 'wan3':
        common.update(size='9:16', audio=True, generation_type='frame', image_urls=[image_url])
    elif job['slug'] == 'minimax_h3':
        # I2V aspect ratio follows the portrait first frame; the explicit field is
        # accepted but documented as ignored for this MiniMax mode.
        common.update(aspect_ratio='9:16', first_frame_image=image_url)
    else:
        raise b.Blocked('Unsupported pilot model')
    return common


def poll_allow_cdn_deferral(client, api, job, root, state):
    try:
        b.poll(client, api, job, root, state, 7, 1800)
        job.pop('download_error', None)
        b.save_state(root, state)
    except b.Blocked as exc:
        if (job.get('status') == 'download_pending' and job.get('result_url')
                and str(exc).startswith(('Media download failed;', 'Media HTTP '))):
            # A terminal successful generation was verified and its URL persisted.
            # Defer only this CDN transfer, never an uncertain generation.
            if job.get('actual_cost_usd') is not None and b.money(job['actual_cost_usd']) > b.money(job['maximum_charge_usd']):
                job.update(status='billing_violation', reason='Observed final charge exceeds the verified bound')
                b.save_state(root, state)
                raise b.Blocked(job['reason']) from None
            job['download_error'] = str(exc)
            b.save_state(root, state)
            print('Generation complete; download deferred:', job['key'], str(exc), flush=True)
            return
        raise


def execute(config, pilot, prices, root=ROOT, resume=False):
    if not os.environ.get('APIMART_API_KEY'):
        raise b.Blocked('APIMART_API_KEY is not injected; no paid submission')
    state = b.read_state(root)
    api = config['api']
    client = b.Client(os.environ['APIMART_API_KEY'])
    balance = b.account_check(client, api, state, root)
    for old in state['jobs'].values():
        if old['status'] in {'submitting', 'submission_unknown', 'billing_violation'}:
            raise b.Blocked('An uncertain submission or billing violation blocks new work; reconcile it first')
        if old.get('task_id') and old['status'] not in {'completed', 'failed'}:
            poll_allow_cdn_deferral(client, api, old, root, state)
            balance = b.account_check(client, api, state, root)
    if any(j['status'] == 'billing_violation' for j in state['jobs'].values()):
        raise b.Blocked('A resumed task exceeded its cost bound; no further paid submissions')
    if resume:
        return
    jobs = jobs_for(config, pilot, prices)
    remaining = [job for job in jobs if job['key'] not in state['jobs']]
    b.ensure_budget(state, sum((b.charge_bound(job) for job in remaining), b.Decimal(0)), balance)
    urls = {}
    for test, spec in pilot['tests'].items():
        if any(j['test'] == test for j in remaining):
            urls[test] = upload(root, state, spec)
            print('Reference uploaded/reused:', test, flush=True)
    for job in remaining:
        if not b.fresh(job['checked_at'], hours=1):
            raise b.Blocked('Pricing quote expired; refresh prices before another paid submission')
        balance = b.account_check(client, api, state, root)
        bound = b.charge_bound(job)
        b.ensure_budget(state, bound, balance)
        request_payload = payload(job, urls[job['test']])
        job.update(status='submitting', authorized_usd=str(bound), submitted_at=b.now(),
            submitted_epoch=time.time(), actual_cost_usd=None,
            request_sha256=hashlib.sha256(json.dumps(request_payload, sort_keys=True).encode()).hexdigest())
        state['jobs'][job['key']] = job
        b.save_state(root, state)
        try:
            response = client.request('POST', api['generation_path'], request_payload)
            task_id = b.pointer(response, api['submission_task_id_pointer'])
            if not isinstance(task_id, str) or not task_id.strip():
                raise b.Blocked('No usable task ID')
            job.update(status='pending', task_id=task_id)
            b.save_state(root, state)
        except Exception:
            job.update(status='submission_unknown', reason='Paid submission outcome uncertain; do not automatically repeat')
            b.save_state(root, state)
            raise b.Blocked(job['reason']) from None
        print('Submitted:', job['key'], 'task:', task_id, 'authorized USD:', bound, flush=True)
        after_submit = b.account_check(client, api, state, root)
        decreased = max(b.Decimal(0), b.money(balance) - b.money(after_submit))
        job['observed_balance_decrease_after_submit_usd'] = str(decreased)
        b.save_state(root, state)
        poll_allow_cdn_deferral(client, api, job, root, state)
        b.account_check(client, api, state, root)
        print('Finished:', job['key'], job['status'], 'actual USD:', job.get('actual_cost_usd'), flush=True)
        report(config, pilot, prices, root)
        if job['status'] == 'billing_violation' or decreased > bound:
            raise b.Blocked('Unexpected cost or reservation: current task retained; all further paid submissions stopped')


def report(config, pilot, prices, root=ROOT):
    state = b.read_state(root)
    folder = root / 'results/reference'
    folder.mkdir(parents=True, exist_ok=True)
    all_jobs = []
    for test, spec in pilot['tests'].items():
        for model in config['models']:
            key = f'reference/{test}/{model["slug"]}'
            old = state['jobs'].get(key)
            row = {'key': test + '/' + model['slug'], 'test': test, 'slug': model['slug'],
                'name': model['name'], 'model_id': model['model_id'], 'scores': dict.fromkeys(b.WEIGHTS),
                'prompt': spec['prompt'], 'mode': pilot['mode'], 'reference_file': '../../' + spec['reference'],
                'status': 'skipped', 'reason': 'Not included in the bounded four-clip pilot; no charge.'}
            if old:
                row.update({k: v for k, v in old.items() if k not in {'task_id', 'result_url', 'request_sha256'}})
                row['key'] = test + '/' + model['slug']
                if old.get('file'):
                    row['file'] = str(Path(old['file']).relative_to('reference'))
                row['reference_file'] = '../../' + spec['reference']
                row['reason'] = old.get('reason') or old.get('download_error')
            all_jobs.append(row)
    costs = [b.money(j['actual_cost_usd']) for key, j in state['jobs'].items()
             if key.startswith('reference/') and j.get('actual_cost_usd') is not None]
    pilot_authorized = sum((b.money(j['authorized_usd']) for key, j in state['jobs'].items()
                            if key.startswith('reference/')), b.Decimal(0))
    completed = sum(j['status'] == 'completed' for j in all_jobs)
    selected_rows = [j for j in all_jobs if j['slug'] in SELECTED]
    technical_pass = all(j.get('technical', {}).get('audio_present') and j.get('technical', {}).get('portrait_9_16')
                         for j in selected_rows)
    result = {'generated_at': b.now(), 'name': pilot['name'], 'requested_jobs': 4,
        'comparison_slots': 8, 'completed_jobs': completed, 'benchmark_complete': completed == 4 and technical_pass,
        'authorized_limit_usd': str(b.LIMIT), 'conservative_committed_usd': str(pilot_authorized),
        'global_conservative_committed_usd': str(b.used_budget(state)), 'global_authorized_limit_usd': str(b.total_authorized(state)),
        'known_actual_cost_usd': str(sum(costs, b.Decimal(0))),
        'actual_cost_complete': all(j.get('actual_cost_usd') is not None for key, j in state['jobs'].items() if key.startswith('reference/')),
        'remaining_balance_usd': state['account_checks'][-1]['available_usd'] if state['account_checks'] else None,
        'rubric_weights': b.WEIGHTS, 'blockers': [], 'jobs': all_jobs,
        'assessment': 'Technical properties measured; qualitative audio/lip-sync/motion scores pending human review.',
        'reference_provenance': 'Two original synthetic stills generated with the image generation tool, outside API Mart credits. No real person likeness supplied.'}
    if any(j.get('status') in {'submission_unknown', 'billing_violation'} for j in state['jobs'].values()):
        result['blockers'].append('An unresolved paid submission or charge requires reconciliation.')
    result['blockers'].extend(sorted({j['download_error'] for j in state['jobs'].values() if j.get('download_error')}))
    b.atomic_json(folder / 'results.json', result)
    b.atomic_json(folder / 'pricing.json', prices)
    b.write_csv(folder / 'costs.csv', all_jobs, ['key', 'model_id', 'status', 'estimate_usd', 'maximum_charge_usd',
        'maximum_reservation_usd', 'authorized_usd', 'actual_cost_usd', 'generation_elapsed_seconds', 'reason'])
    metrics = [dict(key=j['key'], **j.get('technical', {})) for j in all_jobs]
    b.write_csv(folder / 'technical_metrics.csv', metrics, ['key', 'duration_seconds', 'width', 'height', 'frame_rate',
        'video_codec', 'audio_codec', 'audio_present', 'audio_sample_rate', 'mean_volume_db', 'silence_percentage',
        'file_size_bytes', 'portrait_9_16', 'contact_sheet'])
    template = (root / 'templates/comparison.html').read_text()
    data = json.dumps(result).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    viewer = template.replace('__BENCHMARK_DATA__', data).replace('AI video quality benchmark', 'Reference-guided video pilot')
    viewer = viewer.replace("data.completed_jobs+'/8 real videos completed.", "data.completed_jobs+'/4 pilot videos completed.")
    viewer = viewer.replace("storeKey='apimart-video-benchmark-scores-v1'", "storeKey='apimart-reference-pilot-scores-v1'")
    (folder / 'comparison.html').write_text(viewer)
    lines = ['# Reference-guided API Mart pilot', '', f'Completed: {completed}/4 selected videos.',
        f'Known billed total for this four-clip pilot: ${result["known_actual_cost_usd"]}.',
        f'Latest available account/token minimum balance: ${result["remaining_balance_usd"]}.',
        f'Pilot conservative authorization committed: ${pilot_authorized} of $6.00. '
        f'All rounds combined: ${b.used_budget(state)} of ${b.total_authorized(state)} authorized.', '',
        'This is a separate image-to-video pilot, not the original eight text-only benchmark videos. '
        'Two synthetic opening-frame references and expanded timed prompts are used consistently across Wan3 and MiniMax H3. '
        'Gemini and Seedance were not included in this bounded pilot. No separate TTS/music/audio service was used.', '',
        '| Clip | Status | Billed USD | Duration | Dimensions | Audio |', '|---|---|---|---|---|---|']
    for j in all_jobs:
        m = j.get('technical', {})
        lines.append(f'| {j["key"]} | {j["status"]} | {j.get("actual_cost_usd", "—")} | {m.get("duration_seconds", "—")} | {m.get("width", "—")}×{m.get("height", "—")} | {m.get("audio_present", "—")} |')
    lines += ['', '## Review', '', 'All six qualitative rubric scores remain pending human review. Inspect the actual clips and native audio for exact wording, '
              'lip sync, three synchronized landings/notes, anatomy, face identity and continuity. Contact sheets and loudness cannot establish these qualities.', '',
              'Input references are stored in ../../references/. Detailed prompts: ../../config/reference-tests.json. '
              'Original MP4 downloads are unchanged. Private shared task IDs/result URLs are in ../../.runtime/state.json (excluded from archives).', '',
              'Resume from video-benchmark/ with `python3 reference_tests.py resume`. It never issues a paid generation POST. '
              'Execute checks existing ledger keys before submitting any new job; never delete the shared ledger to rerun. '
              'The $6 authorization is shared with benchmark.py, not reset for this pilot.', '',
              'Pricing uses live public default payable rates for estimates and the higher undiscounted rates for maximum client authorization, '
              'plus 25%. One MiniMax input image is within its documented free-image allowance. '
              'Reservation is estimated from the fixed-duration price; the balance is read immediately after submission and new jobs stop '
              'on an unexpectedly large decrease. A client cannot enforce a provider-side billing cap.']
    (folder / 'report.md').write_text('\n'.join(lines) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['dry-run', 'execute', 'resume', 'report'])
    args = parser.parse_args()
    config, _ = b.load()
    pilot = settings()
    with b.locked(ROOT):
        price_file = ROOT / 'results/reference/pricing.json'
        prices = json.loads(price_file.read_text()) if price_file.exists() else {}
        try:
            if args.command in {'dry-run', 'execute'}:
                prices = get_prices()
                jobs = jobs_for(config, pilot, prices)
                for j in jobs:
                    print(j['key'], 'estimate USD', j['estimate_usd'], 'maximum USD', j['maximum_charge_usd'],
                          'with margin USD', b.charge_bound(j), flush=True)
                total = sum((b.charge_bound(j) for j in jobs if j['key'] not in b.read_state(ROOT)['jobs']), b.Decimal(0))
                b.ensure_budget(b.read_state(ROOT), total)
                print('Remaining new authorization USD:', total, flush=True)
            if args.command in {'execute', 'resume'}:
                execute(config, pilot, prices, resume=args.command == 'resume')
                b.analyze(ROOT)
            result = report(config, pilot, prices)
            print('Completed real pilot videos:', result['completed_jobs'], '/4', flush=True)
            return 0
        except b.Blocked as exc:
            report(config, pilot, prices)
            print('BLOCKED:', str(exc), file=sys.stderr)
            return 2


if __name__ == '__main__':
    sys.exit(main())
