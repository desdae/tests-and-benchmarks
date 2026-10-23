#!/usr/bin/env python3
"""Round two: two premium candidates, full vertical and infographic-safe layouts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import benchmark as b
import reference_tests as ref

ROUND = 'shorts_round2'
ROUND_CAP = b.Decimal('6')
GLOBAL_CAP = b.Decimal('12')
MODELS = {'veo_quality': 'veo3.1-quality-official', 'kling_v4': 'kling-v4'}


def config(root=b.ROOT):
    cfg = json.loads((root / 'config/shorts-round2.json').read_text())
    if cfg['round_id'] != ROUND or b.money(cfg['new_authorization_usd']) != ROUND_CAP or b.money(cfg['global_authorization_ceiling_usd']) != GLOBAL_CAP:
        raise b.Blocked('Round authorization differs from the explicit additional $6 authorization')
    if {k: v['model_id'] for k, v in cfg['models'].items()} != MODELS or set(cfg['layouts']) != {'full', 'lower'}:
        raise b.Blocked('Unexpected model or layout substitution')
    if cfg['duration_seconds'] != 4:
        raise b.Blocked('Only the priced four-second plan is authorized by this runner')
    return cfg


def round_used(state):
    return sum((b.money(j['authorized_usd']) for k, j in state['jobs'].items() if k.startswith(ROUND + '/')), b.Decimal(0))


def ensure(state, amount, available=None):
    if round_used(state) + amount > ROUND_CAP:
        raise b.Blocked('Additional round exceeds $6 with the required 25% safety margin')
    if b.used_budget(state) + amount > GLOBAL_CAP:
        raise b.Blocked('Shared ledger exceeds the original plus additional authorization')
    if available is not None and amount > b.money(available):
        raise b.Blocked('Provider balance cannot cover the conservative remaining plan')


def prices(cfg):
    quotes = {}
    if not b.fresh(cfg['documentation_verified_at']):
        raise b.Blocked('Refresh official parameter and billing documentation before new paid work')
    for slug, spec in cfg['models'].items():
        url = 'https://api.apimart.ai/api/pricing/model?' + urllib.parse.urlencode({'model': spec['model_id']})
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'CodexVideoBenchmark/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            d = result['data']
            if result.get('success') is not True or d['model_name'] != spec['model_id'] or d['billing_type'] != 'per_second':
                raise b.Blocked('Current price no longer matches the documented fixed-per-second contract')
            resolution = spec['resolution'].upper()
            if slug == 'veo_quality':
                listed = b.money(d['billing_matrix'][resolution]['audio'])
                payable = b.money(d['billing_matrix_paid_prices'][resolution]['audio'])
            else:
                listed = b.money(d['resolution_prices'][resolution])
                payable = b.money(d['resolution_paid_prices'][resolution])
            if listed <= 0 or payable <= 0 or payable > listed:
                raise b.Blocked('Unexpected price factor; safe cost ceiling not established')
        except (OSError, ValueError, KeyError):
            raise b.Blocked('Current model/audio pricing could not be verified') from None
        quotes[slug] = {'estimate_usd': str(payable * 4), 'maximum_charge_usd': str(listed * 4),
            'maximum_reservation_usd': str(listed * 4), 'price_checked_at': b.now(), 'pricing_source': url,
            'pricing_basis': '4 output seconds, one first-frame image, no video/audio references; '
                'Veo audio-inclusive matrix tier, Kling always includes stereo audio. Higher undiscounted rate '
                'sets conservative authorization plus 25%; not a provider-enforced cap.'}
    return quotes


def jobs(cfg, quotes):
    return [{'key': f'{ROUND}/{layout}/{slug}', 'round': ROUND, 'layout': layout, 'slug': slug,
        'model_id': spec['model_id'], 'name': spec['name'], 'resolution': spec['resolution'],
        'prompt': scene['prompt'], 'reference_file': scene['reference'], 'status': 'planned',
        **quotes[slug]} for layout, scene in cfg['layouts'].items() for slug, spec in cfg['models'].items()]


def payload(job, image_url):
    request = {'model': job['model_id'], 'prompt': job['prompt'], 'duration': 4,
        'resolution': job['resolution'], 'aspect_ratio': '9:16', 'first_frame_image': image_url}
    if job['slug'] == 'veo_quality':
        request.update(generate_audio=True, sample_count=1, person_generation='allow_adult', resize_mode='pad')
    elif job['slug'] != 'kling_v4':
        raise b.Blocked('Unexpected model')
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
    state.setdefault('additional_authorizations', {}).setdefault(ROUND, {
        'authorized_at': b.now(), 'new_round_limit_usd': '6', 'global_limit_usd': '12',
        'source': 'Explicit user authorization: Allow up to $6 additional; 9:16 with clear upper half'})
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


def export_filter(layout):
    filters = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x101827,setsar=1'
    if layout == 'lower':
        filters += ',drawbox=x=0:y=0:w=iw:h=ih/2:color=0x101827:t=fill'
    return filters


def export(root=b.ROOT):
    state = b.read_state(root)
    for key, job in state['jobs'].items():
        if not key.startswith(ROUND + '/') or not job.get('file'):
            continue
        original = root / 'results' / job['file']
        target = root / 'results' / ROUND / 'exports' / job['layout'] / (job['slug'] + '.mp4')
        target.parent.mkdir(parents=True, exist_ok=True)
        b.process(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(original),
            '-map', '0:v:0', '-map', '0:a:0', '-vf', export_filter(job['layout']),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-threads', '2',
            '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(target)])
        metrics = b.analyze_video(target)
        if (metrics['width'], metrics['height']) != (1080, 1920) or not metrics['audio_present']:
            raise b.Blocked('Delivery export dimensions or audio stream failed validation')
        if job['layout'] == 'lower':
            checked = b.process(['ffmpeg', '-hide_banner', '-nostats', '-i', str(target),
                '-vf', 'crop=iw:ih/2:0:0,signalstats,metadata=print', '-an', '-f', 'null', '-']).stderr
            minima = [float(v) for v in re.findall(r'lavfi.signalstats.YMIN=([\d.]+)', checked)]
            maxima = [float(v) for v in re.findall(r'lavfi.signalstats.YMAX=([\d.]+)', checked)]
            if not minima or len(minima) != len(maxima):
                raise b.Blocked('Upper-half uniformity check did not execute')
            metrics['upper_half_luma_range_max'] = max(hi - lo for lo, hi in zip(minima, maxima))
            if metrics['upper_half_luma_range_max'] > 3:
                raise b.Blocked('Upper-half delivery canvas is not uniform')
        job.update(delivery_file=str(target.relative_to(root / 'results')), delivery_technical=metrics,
            delivery_note='Exact 1080x1920 export. Native AAC audio stream copied unchanged. '
                + ('Upper 960 rows replaced with solid #101827 for infographic compositing.' if job['layout'] == 'lower'
                   else 'Native video scaled/padded to exact vertical canvas; Kling is upscaled from 720p.'))
    b.save_state(root, state)


def report(cfg, quotes, root=b.ROOT):
    state = b.read_state(root)
    folder = root / 'results' / ROUND
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for layout, scene in cfg['layouts'].items():
        for slug, model in cfg['models'].items():
            key = f'{ROUND}/{layout}/{slug}'
            row = {'key': ('speech' if layout == 'full' else 'music') + '/' + slug,
                'test': 'speech' if layout == 'full' else 'music', 'layout': layout, 'slug': slug,
                'name': model['name'], 'model_id': model['model_id'], 'status': 'planned',
                'prompt': scene['prompt'], 'reference_file': '../../' + scene['reference'],
                'scores': dict.fromkeys(b.WEIGHTS), **quotes.get(slug, {})}
            old = state['jobs'].get(key)
            if old:
                public = {k: v for k, v in old.items() if k not in {'task_id', 'result_url', 'request_sha256', 'key', 'reference_file'}}
                row.update(public)
                if old.get('file'):
                    row['original_file'] = str(Path(old['file']).relative_to(ROUND))
                    row['file'] = str(Path(old.get('delivery_file', old['file'])).relative_to(ROUND))
                    row['native_technical'] = old.get('technical')
                    if old.get('delivery_file') and old.get('delivery_technical'):
                        row['technical'] = dict(old['delivery_technical'])
                        row['technical']['contact_sheet'] = 'exports/' + old['delivery_technical']['contact_sheet']
                row['duration_note'] = old.get('delivery_note', 'Native source; exact 1080x1920 export pending')
                row['reason'] = old.get('reason') or old.get('download_error')
            rows.append(row)
    completed = sum(j['status'] == 'completed' for j in rows)
    billed = sum((b.money(j['actual_cost_usd']) for j in rows if j.get('actual_cost_usd') is not None), b.Decimal(0))
    data = {'generated_at': b.now(), 'round_id': ROUND, 'requested_jobs': 4, 'completed_jobs': completed,
        'exports_complete': all(j.get('delivery_file') for j in rows),
        'known_actual_cost_usd': str(billed), 'actual_cost_complete': all(j.get('actual_cost_usd') is not None for j in rows),
        'conservative_committed_usd': str(round_used(state)), 'authorized_limit_usd': '6',
        'remaining_balance_usd': state['account_checks'][-1]['available_usd'] if state['account_checks'] else None,
        'rubric_weights': b.WEIGHTS, 'blockers': sorted({j['download_error'] for j in rows if j.get('download_error')}),
        'jobs': rows, 'selection': 'Two current premium candidates, not an independently established quality ranking.',
        'quality_assessment': 'Native audio presence and technical properties measured. Exact wording, lip sync and aesthetics pending playback review.'}
    validation = folder / 'validation.json'
    if validation.exists():
        data['validation'] = json.loads(validation.read_text())
    b.atomic_json(folder / 'results.json', data)
    b.atomic_json(folder / 'pricing.json', quotes)
    b.write_csv(folder / 'costs.csv', rows, ['layout', 'model_id', 'status', 'estimate_usd', 'maximum_charge_usd',
        'authorized_usd', 'actual_cost_usd', 'generation_elapsed_seconds', 'reason'])
    b.write_csv(folder / 'technical_metrics.csv', [dict(layout=j['layout'], model_id=j['model_id'], **(j.get('native_technical') or j.get('technical', {}))) for j in rows],
        ['layout', 'model_id', 'duration_seconds', 'width', 'height', 'frame_rate', 'audio_present', 'audio_codec',
         'audio_sample_rate', 'mean_volume_db', 'silence_percentage', 'file_size_bytes'])
    template = (root / 'templates/comparison.html').read_text()
    template = template.replace('AI video quality benchmark', 'Shorts and Reels: premium model layout tests')
    template = template.replace('Four models · two shared prompts · native audio · portrait video', 'Two premium candidates · two vertical layouts · native audio · 1080×1920 delivery exports')
    template = template.replace('>Speech</button>', '>Full vertical</button>').replace('>Music</button>', '>Clear upper half</button>')
    template = template.replace('Speech / 10', 'Full / 10').replace('Music / 10', 'Lower / 10')
    template = template.replace("data.completed_jobs+'/8 real videos completed.", "data.completed_jobs+'/4 new videos completed.")
    template = template.replace("storeKey='apimart-video-benchmark-scores-v1'", "storeKey='apimart-shorts-round2-scores-v1'")
    template = template.replace('The speech test requires exact words and lip synchronization. The music test requires three landings with distinct synchronized footsteps and marimba notes.',
        'Both layouts use the same spoken line. Inspect identity, exact words and lip synchronization; the lower-positioned layout must keep the speaker below the halfway line. Delivery exports contain a solid upper-half canvas for infographics; original native outputs are retained separately.')
    needle = "card.append(el('p',j.duration_note));"
    template = template.replace(needle, needle + "if(j.native_technical){const n=j.native_technical;card.append(el('p','Native source: '+n.width+' × '+n.height+' · '+n.frame_rate+' fps'));}if(j.original_file){const a=el('a','Open original native output');a.href=j.original_file;card.append(a);}")
    encoded = json.dumps(data).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    (folder / 'comparison.html').write_text(template.replace('__BENCHMARK_DATA__', encoded))
    lines = ['# Shorts/Reels round two', '', f'Native clips downloaded: {completed}/4; delivery exports complete: {data["exports_complete"]}.',
        f'New-round billed USD: {billed}. New-round conservative authorization: {round_used(state)} / 6.',
        f'Latest available balance USD: {data["remaining_balance_usd"]}.', '',
        'Veo 3.1 Quality Official (1080p, native audio enabled) and Kling V4 (720p, native stereo audio) are premium '
        'candidates selected from current documentation. This does not establish that either is the best-performing model.', '',
        'Each model gets a four-second full-screen portrait reference and a separate lower-positioned presenter reference. '
        'The same new synthetic presenter and exact sentence are used throughout: **Small daily steps lead to lasting change.**', '',
        'Original native outputs are unchanged in full/ and lower/. Exact 1080×1920 delivery exports are in exports/full/ and exports/lower/. '
        'Kling exports are upscaled from native 720p; no claim of native 1080p detail. Lower-layout delivery exports '
        'replace the top 960 rows with solid #101827, guaranteeing a clean infographic canvas. '
        'AAC audio is copied unchanged; no separate TTS or replacement audio.', '',
        '| Layout | Model | Status | Billed USD | Native size | Export |', '|---|---|---|---|---|---|']
    for j in rows:
        m = j.get('native_technical') or j.get('technical', {})
        lines.append(f'| {j["layout"]} | {j["model_id"]} | {j["status"]} | {j.get("actual_cost_usd", "unknown")} | {m.get("width", "—")}×{m.get("height", "—")} | {bool(j.get("delivery_file"))} |')
    lines += ['', 'Qualitative scores, exact wording and lip synchronization remain pending human playback review. '
        'The viewer includes references, full prompts, manual scoring and links to the original native outputs.', '',
        'Resume existing tasks with `python3 shorts_tests.py resume`; no paid POST is sent. '
        'Completed or failed ledger keys never automatically regenerate. Missing private ledger blocks fresh-clone execution. '
        'The explicit additional $6 round authorization and original $6 authorization share the private ledger; '
        'the new round separately enforces its own $6 cap and 25% margin. No deposits or automatic recharge.', '',
        'Configuration/prompts: ../../config/shorts-round2.json. References: ../../references/round2-full.png and round2-lower.png.']
    (folder / 'report.md').write_text('\n'.join(lines) + '\n')
    return data


def package(root=b.ROOT):
    target = root.parent / 'shorts-round2-results.zip'
    items = [p for p in (root / 'results' / ROUND).rglob('*') if p.is_file()]
    items += [root / f for f in ['benchmark.py', 'reference_tests.py', 'shorts_tests.py', 'requirements.txt',
        'templates/comparison.html', 'references/round2-full.png', 'references/round2-lower.png']]
    items += list((root / 'config').glob('*.json'))
    items += list((root / 'tests').glob('*.py'))
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('SHORTS-ROUND2-README.md',
            '# Shorts and Reels layout tests\n\n'
            'Open video-benchmark/results/shorts_round2/comparison.html after extracting the complete archive.\n\n'
            'Veo 3.1 Quality Official and Kling V4, four seconds each, native model-generated speech. '
            'Each has normal full vertical and lower-positioned presenter compositions using new synthetic reference stills.\n\n'
            'Original native MP4s: video-benchmark/results/shorts_round2/full/ and lower/.\n'
            'Exact 1080x1920 exports: video-benchmark/results/shorts_round2/exports/full/ and exports/lower/. '
            'Lower-layout exports have an opaque #101827 upper 960-pixel region for infographic compositing. '
            'Kling exports upscale native 720p; native AAC audio is copied unchanged.\n\n'
            'Detailed prompts and authorization: video-benchmark/config/shorts-round2.json. '
            'References: video-benchmark/references/round2-full.png and round2-lower.png. '
            'Current actual costs, native/export metrics and manual scoring are in the results folder.\n\n'
            'These are premium model candidates, not a proven best-model ranking. Lip sync, exact spoken wording '
            'and qualitative scores need playback review. No separate TTS, audio replacement or music generation was used.\n\n'
            'Private task IDs, temporary result URLs and the shared spending ledger are excluded from this archive. '
            'The CLI blocks if completed public results exist without the original private ledger; '
            'do not regenerate to replace missing state. Use the existing cloud environment to resume live operations. '
            'No API key is included. The previous pilot media are in a separate earlier bundle.\n')
        for path in sorted(set(items)):
            archive.write(path, Path('video-benchmark') / path.relative_to(root))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['dry-run', 'execute', 'resume', 'report', 'export', 'package'])
    args = parser.parse_args()
    cfg = config()
    api = b.load()[0]['api']
    with b.locked(b.ROOT):
        path = b.ROOT / 'results' / ROUND / 'pricing.json'
        quotes = json.loads(path.read_text()) if path.exists() else {}
        try:
            if args.command in {'dry-run', 'execute'}:
                quotes = prices(cfg)
                remaining = [j for j in jobs(cfg, quotes) if j['key'] not in b.read_state(b.ROOT)['jobs']]
                for job in remaining:
                    print(job['key'], 'estimated USD', job['estimate_usd'], 'with upper-rate margin USD', b.charge_bound(job), flush=True)
                total = sum((b.charge_bound(j) for j in remaining), b.Decimal(0))
                ensure(b.read_state(b.ROOT), total)
                print('Remaining new-round authorization USD:', total, flush=True)
            if args.command in {'execute', 'resume'}:
                execute(cfg, quotes, api, resume=args.command == 'resume')
                b.analyze(b.ROOT)
                export()
            elif args.command == 'export':
                export()
            result = report(cfg, quotes)
            if args.command == 'package':
                print(package())
            print('Native outputs downloaded:', result['completed_jobs'], '/4; delivery exports:', result['exports_complete'])
            return 0
        except b.Blocked as exc:
            report(cfg, quotes)
            print('BLOCKED:', str(exc), file=sys.stderr)
            return 2


if __name__ == '__main__':
    sys.exit(main())
