#!/usr/bin/env python3
"""Fail-closed API Mart benchmark. No paid POST is retried, even after a timeout."""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
LIMIT = Decimal('6.00')
MARGIN = Decimal('1.25')
EXPECTED = {'wan3': 'wan3.0-video', 'minimax_h3': 'MiniMax-H3',
            'gemini_omni': 'gemini-omni-1.1-flash', 'seedance25': 'seedance-2.5'}
WEIGHTS = {'Visual realism': .25, 'Motion quality': .25, 'Prompt adherence': .20,
           'Temporal consistency': .15, 'Audio quality and synchronization': .10,
           'Cost efficiency': .05}


class Blocked(RuntimeError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def money(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise Blocked('Missing or invalid USD cost bound') from exc
    if not result.is_finite() or result < 0:
        raise Blocked('USD amounts must be finite and nonnegative')
    return result


def pointer(data, path):
    """RFC 6901 JSON pointer; response paths must come from verified documentation."""
    if path is None:
        return None
    if path == '':
        return data
    if not isinstance(path, str) or not path.startswith('/'):
        raise Blocked('Invalid documented JSON pointer')
    try:
        for part in path[1:].split('/'):
            part = part.replace('~1', '/').replace('~0', '~')
            data = data[int(part)] if isinstance(data, list) else data[part]
        return data
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise Blocked('Documented response field is missing') from exc


def fresh(stamp, hours=24):
    try:
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(stamp)
        return dt.timedelta(0) <= age <= dt.timedelta(hours=hours)
    except (ValueError, TypeError):
        return False


def atomic_json(path, data, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.write-')
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, indent=2, allow_nan=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, 0o600 if private else 0o644)
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked(root):
    folder = root / '.runtime'
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    with (folder / 'lock').open('a') as handle:
        os.chmod(handle.name, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Blocked('Another benchmark process holds the submission lock') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, key, opener=None, sleep=time.sleep):
        if not key:
            raise Blocked('APIMART_API_KEY is unavailable; enter it securely in environment settings')
        self._key = key
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.sleep = sleep

    def request(self, method, path, payload=None):
        # Never allow credentials onto a redirect or any other origin.
        if not path.startswith('/v1/') or '?' in path or '#' in path or '..' in path:
            raise Blocked('Only documented /v1/ API paths are accepted')
        body = None if payload is None else json.dumps(payload).encode()
        attempts = 3 if method == 'GET' else 1
        for attempt in range(attempts):
            req = urllib.request.Request('https://api.apimart.ai' + path, data=body,
                headers={'Authorization': 'Bearer ' + self._key,
                         'Content-Type': 'application/json', 'Accept': 'application/json',
                         'User-Agent': 'CodexVideoBenchmark/1.0'}, method=method)
            try:
                with self.opener.open(req, timeout=45) as response:
                    return json.loads(response.read(4 * 1024 * 1024))
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                if method == 'GET' and (code == 429 or 500 <= code <= 599) and attempt + 1 < attempts:
                    self.sleep(2 ** attempt)
                    continue
                messages = {401: 'authentication rejected', 402: 'insufficient credits',
                            403: 'access or network policy denied', 429: 'rate limited'}
                raise Blocked(f'API HTTP {code}: {messages.get(code, "request failed")}') from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if method == 'GET' and attempt + 1 < attempts:
                    self.sleep(2 ** attempt)
                    continue
                raise Blocked('API transport failure; check api.apimart.ai network access') from None
            except (ValueError, UnicodeError):
                raise Blocked('API returned invalid JSON; response body withheld') from None


def evidence_valid(obj, required):
    evidence = obj.get('evidence')
    if not fresh(obj.get('verified_at')) or not isinstance(evidence, dict):
        return False
    sources = evidence.get('sources', [])
    return (all(evidence.get(item) is True for item in required)
            and bool(sources) and all(isinstance(s, str) and
            (s.startswith('https://docs.apimart.ai/') or s.startswith('https://apimart.ai/')) for s in sources))


def model_problem(model):
    if model.get('slug') not in EXPECTED or EXPECTED[model['slug']] != model.get('model_id'):
        return 'Model substitution or unknown model ID is prohibited'
    required = ['availability', 'parameters', 'native_audio', 'pricing', 'reservation_bound', 'duration_bound']
    if not evidence_valid(model, required):
        return model.get('skip_reason') or 'Current model documentation and cost bounds are unverified'
    template = model.get('request_template')
    if not isinstance(template, dict) or template.get('model') != model['model_id'] or template.get('prompt') != '{prompt}':
        return 'Verified request template with exact model and prompt placeholder is required'
    if 'n' in template and template['n'] != 1:
        return 'Only one output per request is permitted'
    try:
        maximum = money(model.get('maximum_charge_usd'))
        reservation = money(model.get('maximum_reservation_usd'))
        estimate = money(model.get('estimate_usd'))
        duration = money(model.get('output_duration_upper_bound_seconds'))
        if maximum <= 0 or maximum < estimate or reservation < maximum or duration <= 0:
            return 'Charge, reservation, estimate, or duration bounds are inconsistent'
    except Blocked as exc:
        return str(exc)
    return None


def api_problem(api):
    if api.get('origin') != 'https://api.apimart.ai':
        return 'Unsupported API origin'
    if api.get('generation_path') != '/v1/videos/generations' or api.get('task_path') != '/v1/tasks/{task_id}':
        return 'Generation or polling path differs from the requested workflow; review documentation'
    if not evidence_valid(api, ['authentication', 'response_formats', 'read_only_probe', 'billing']):
        return 'Authentication probe and response/billing schemas need current official documentation'
    for field in ['auth_probe_path', 'submission_task_id_pointer', 'task_status_pointer', 'video_url_pointer']:
        if not api.get(field):
            return f'Missing documented API mapping: {field}'
    statuses = api.get('statuses')
    if not isinstance(statuses, dict) or any(not statuses.get(k) for k in ['pending', 'completed', 'failed']):
        return 'Documented task status values are missing'
    if api.get('actual_cost_pointer') is not None and api.get('actual_cost_currency') != 'USD':
        return 'Billing amount must be documented in USD; credit conversion is not assumed'
    if api.get('balance_path') and (not api.get('balance_pointer') or api.get('balance_currency') != 'USD'
                                    or api.get('balance_semantics') != 'available_usd'):
        return 'Balance must be documented as available USD'
    return None


def charge_bound(job):
    return max(money(job['maximum_charge_usd']), money(job['maximum_reservation_usd'])) * MARGIN


def used_budget(state):
    # Retain the whole conservative reservation for failures and unknown outcomes.
    # A refund or a smaller final charge never replenishes authorization automatically.
    return sum((money(j['authorized_usd']) for j in state.get('jobs', {}).values()), Decimal(0))


def total_authorized(state):
    return LIMIT + sum((money(a['new_round_limit_usd'])
                        for a in state.get('additional_authorizations', {}).values()), Decimal(0))


def ensure_budget(state, bound, balance=None):
    if used_budget(state) + bound > LIMIT:
        raise Blocked('Next job exceeds the remaining $6 authorization with safety margin')
    if balance is not None and bound > money(balance):
        raise Blocked('Available provider balance is below the conservative reservation')


def load(root=ROOT):
    config = json.loads((root / 'config/models.json').read_text())
    prompts = json.loads((root / 'config/prompts.json').read_text())
    if money(config['budget_usd']) != LIMIT or money(config['safety_multiplier']) < MARGIN:
        raise Blocked('This benchmark requires a fixed $6 limit and at least 25% safety margin')
    if config['safety_multiplier'] != '1.25':
        raise Blocked('Change implementation and re-review budget to use another safety multiplier')
    if {m['slug']: m['model_id'] for m in config['models']} != EXPECTED or len(config['models']) != 4:
        raise Blocked('Exactly the four requested models are required')
    if set(prompts) != {'speech', 'music'}:
        raise Blocked('Exactly the speech and music prompts are required')
    return config, prompts


def plan(config, prompts):
    jobs = []
    api_error = api_problem(config['api'])
    for test, prompt in prompts.items():
        for model in config['models']:
            reason = model_problem(model) or api_error
            jobs.append({'key': test + '/' + model['slug'], 'test': test, 'slug': model['slug'],
                'model_id': model['model_id'], 'name': model['name'], 'prompt': prompt,
                'estimate_usd': model.get('estimate_usd'),
                'maximum_charge_usd': model.get('maximum_charge_usd'),
                'maximum_reservation_usd': model.get('maximum_reservation_usd'),
                'status': 'skipped' if reason else 'planned', 'reason': reason,
                'scores': {name: None for name in WEIGHTS},
                'target_resolution': model['target_resolution'],
                'target_duration_seconds': model['target_duration_seconds'],
                'duration_note': 'Natural variable duration; must have documented charge and duration bounds' if model['slug'] == 'gemini_omni' else 'Target 5 seconds'})
    total = sum((charge_bound(j) for j in jobs if j['status'] == 'planned'), Decimal(0))
    if total > LIMIT:
        for job in jobs:
            if job['status'] == 'planned':
                job.update(status='skipped', reason='Full verified plan exceeds $6 including 25% margin')
    return jobs


def read_state(root):
    path = root / '.runtime/state.json'
    if path.exists():
        return json.loads(path.read_text())
    for report in [root / 'results/results.json', root / 'results/reference/results.json',
                   root / 'results/shorts_round2/results.json', root / 'results/economy_round3/results.json', root / 'results/shepherd_round4/results.json']:
        if report.exists():
            public = json.loads(report.read_text())
            if public.get('submitted_or_uncertain', 0) or public.get('completed_jobs', 0):
                raise Blocked('Completed/submitted public results exist but the private spending ledger is missing. '
                              'Restore .runtime/state.json from the original environment; never regenerate to replace missing state. '
                              'Existing HTML reports and videos can be viewed without the ledger.')
    return {'version': 1, 'jobs': {}, 'account_checks': []}


def save_state(root, state):
    atomic_json(root / '.runtime/state.json', state, private=True)


def account_check(client, api, state, root):
    probe = client.request('GET', api['auth_probe_path'])
    if api.get('probe_success_pointer') and pointer(probe, api['probe_success_pointer']) is not True:
        raise Blocked('Read-only authentication probe returned an unsuccessful result')
    record = {'at': now(), 'authenticated': True, 'available_usd': None, 'usage': None}
    if api.get('balance_path'):
        balance_data = probe if api['balance_path'] == api['auth_probe_path'] else client.request('GET', api['balance_path'])
        divisor = money(api.get('balance_divisor', 1))
        if divisor <= 0:
            raise Blocked('Invalid documented balance conversion')
        available = money(pointer(balance_data, api['balance_pointer'])) / divisor
        if api.get('token_balance_pointer') and not pointer(probe, api['token_unlimited_pointer']):
            available = min(available, money(pointer(probe, api['token_balance_pointer'])) / divisor)
        record['available_usd'] = str(available)
    if api.get('usage_path'):
        # Documentation says no more than one usage query per minute.
        previous = next((r for r in reversed(state['account_checks']) if r.get('usage_observed_epoch')), None)
        if previous and time.time() - previous['usage_observed_epoch'] < 60:
            record.update(usage=previous['usage'], usage_observed_epoch=previous['usage_observed_epoch'], usage_reused=True)
        else:
            value = pointer(client.request('GET', api['usage_path']), api['usage_pointer'])
            record.update(usage=str(money(value)), usage_observed_epoch=time.time(), usage_reused=False)
        record['usage_semantics'] = api.get('usage_semantics')
    state['account_checks'].append(record)
    save_state(root, state)
    return record['available_usd']


def valid_media_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise Blocked('Result URL must be HTTPS without embedded credentials')
    if parts.port not in (None, 443) or parts.hostname in {'localhost', 'localhost.localdomain'}:
        raise Blocked('Unsupported media destination')
    try:
        if not ipaddress.ip_address(parts.hostname).is_global:
            raise Blocked('Nonpublic media destination')
    except ValueError:
        pass
    return url


def download(url, target):
    """No Authorization header is ever sent to a CDN, including redirects."""
    target.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirect())
    part = target.with_suffix('.part')
    current = url
    for _ in range(6):
        valid_media_url(current)
        host = urllib.parse.urlsplit(current).hostname
        try:
            with opener.open(urllib.request.Request(current), timeout=60) as response, part.open('wb') as out:
                shutil.copyfileobj(response, out)
            if not part.stat().st_size:
                raise Blocked('Downloaded media is empty')
            os.replace(part, target)
            return
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get('Location'):
                current = urllib.parse.urljoin(current, exc.headers['Location'])
                exc.close()
                continue
            code = exc.code
            exc.close()
            raise Blocked(f'Media HTTP {code}; allow HTTPS host {host}; original URL is preserved privately') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise Blocked(f'Media download failed; check HTTPS host {host}; original URL is preserved privately') from None
    raise Blocked('Too many media redirects; original result URL is preserved privately')


def poll(client, api, job, root, state, poll_seconds=7, timeout=1800):
    if job.get('status') in {'failed', 'submission_unknown', 'billing_violation'}:
        return
    if not job.get('task_id'):
        raise Blocked('Submission has no task ID; reconcile with provider, never resubmit automatically')
    deadline = time.monotonic() + timeout
    path = api['task_path'].replace('{task_id}', urllib.parse.quote(job['task_id'], safe=''))
    while True:
        response = client.request('GET', path)
        status = pointer(response, api['task_status_pointer'])
        job['last_polled_at'] = now()
        if api.get('actual_cost_pointer'):
            try:
                cost = pointer(response, api['actual_cost_pointer'])
            except Blocked:
                cost = None  # A final billing field may be absent until reconciliation.
            if cost is not None and status in api['statuses']['completed'] + api['statuses']['failed']:
                job['actual_cost_usd'] = str(money(cost))
        if status in api['statuses']['failed']:
            job.update(status='failed', reason='Provider task failed; no automatic regeneration')
            if job.get('actual_cost_usd') is not None and money(job['actual_cost_usd']) > money(job['maximum_charge_usd']):
                job.update(status='billing_violation', reason='Observed failed-task charge exceeds documented bound; new submissions stopped')
            save_state(root, state)
            return
        if status in api['statuses']['completed']:
            url = pointer(response, api['video_url_pointer'])
            if not isinstance(url, str):
                raise Blocked('Documented video URL is not a string')
            valid_media_url(url)
            job.update(status='download_pending', result_url=url)
            job.setdefault('generation_elapsed_seconds', round(time.time() - job['submitted_epoch'], 3))
            save_state(root, state)  # Preserve original URL before attempting a CDN request.
            target = root / 'results' / (job['key'] + '.mp4')
            if not target.exists() or not job.get('file'):
                download(url, target)
            job.update(status='completed', file=str(target.relative_to(root / 'results')), completed_at=now())
            if job.get('actual_cost_usd') is not None and money(job['actual_cost_usd']) > money(job['maximum_charge_usd']):
                job.update(status='billing_violation', reason='Observed charge exceeds documented bound; all new submissions stopped')
            save_state(root, state)
            return
        if status not in api['statuses']['pending']:
            raise Blocked('Undocumented provider task status; task retained for reconciliation')
        if job.get('actual_cost_usd') is not None and money(job['actual_cost_usd']) > money(job['maximum_charge_usd']):
            job.update(status='billing_violation', reason='Observed charge exceeds documented bound; new submissions stopped')
            save_state(root, state)
            raise Blocked(job['reason'])
        job['status'] = 'pending'
        save_state(root, state)
        if time.monotonic() >= deadline:
            raise Blocked('Polling timed out; resume the existing task without another paid POST')
        time.sleep(poll_seconds)


def run(config, prompts, root, resume_only=False, poll_seconds=7, timeout=1800):
    if not os.environ.get('APIMART_API_KEY'):
        raise Blocked('APIMART_API_KEY is unavailable; no paid requests were submitted')
    issue = api_problem(config['api'])
    if issue:
        raise Blocked(issue)
    client = Client(os.environ['APIMART_API_KEY'])
    state = read_state(root)
    api = config['api']
    balance = account_check(client, api, state, root)
    # Resolve old work first. No new submission while an earlier task is uncertain.
    for old in state['jobs'].values():
        if old['status'] in {'submitting', 'submission_unknown'}:
            raise Blocked('An earlier submission has an unknown outcome. Reconcile it with API Mart; no resubmission')
        if old['status'] == 'billing_violation':
            raise Blocked('A prior charge exceeded its bound; no further paid requests authorized')
        if old.get('task_id') and (old['status'] not in {'completed', 'failed'} or
                                  (old['status'] == 'completed' and old.get('actual_cost_usd') is None)):
            poll(client, api, old, root, state, poll_seconds, timeout)
            balance = account_check(client, api, state, root)
    if any(j['status'] == 'billing_violation' for j in state['jobs'].values()):
        raise Blocked('Observed charge exceeded its bound; all new submissions stopped')
    if resume_only:
        return
    jobs = plan(config, prompts)
    # Check the whole remaining plan before its first new submission.
    remaining = sum((charge_bound(j) for j in jobs if j['status'] == 'planned' and j['key'] not in state['jobs']), Decimal(0))
    ensure_budget(state, remaining, balance)
    for job in jobs:
        if job['status'] != 'planned' or job['key'] in state['jobs']:
            continue
        # Recheck freshness before every paid request.
        model = next(m for m in config['models'] if m['slug'] == job['slug'])
        issue = model_problem(model) or api_problem(api)
        if issue:
            raise Blocked(issue)
        bound = charge_bound(job)
        balance = account_check(client, api, state, root)
        ensure_budget(state, bound, balance)
        payload = dict(model['request_template'])
        payload['prompt'] = job['prompt']
        job.update(status='submitting', authorized_usd=str(bound), submitted_at=now(),
                   submitted_epoch=time.time(), actual_cost_usd=None,
                   request_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
        state['jobs'][job['key']] = job
        save_state(root, state)  # Durable intent BEFORE any bytes of a paid request.
        try:
            response = client.request('POST', api['generation_path'], payload)
            task_id = pointer(response, api['submission_task_id_pointer'])
            if not isinstance(task_id, str) or not task_id.strip():
                raise Blocked('Submission response lacks a usable task ID')
            job.update(task_id=task_id, status='pending')
            save_state(root, state)
        except Exception:
            job.update(status='submission_unknown', reason='Paid submission outcome uncertain; reconcile with provider, do not repeat')
            save_state(root, state)
            raise Blocked(job['reason']) from None
        poll(client, api, job, root, state, poll_seconds, timeout)
        balance = account_check(client, api, state, root)
        render(root, config, prompts)
        if job['status'] == 'billing_violation':
            raise Blocked(job['reason'])


def process(args):
    completed = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if completed.returncode:
        raise Blocked(f'{Path(args[0]).name} exited {completed.returncode}; technical analysis incomplete')
    return completed


def analyze_video(path):
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
        raise Blocked('FFmpeg and ffprobe are required for technical evaluation')
    probe = json.loads(process(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]).stdout)
    video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
    if not video:
        raise Blocked('Downloaded file has no video stream')
    duration = float(probe['format']['duration'])
    rate = video.get('avg_frame_rate', '0/1').split('/')
    metrics = {'duration_seconds': duration, 'width': video['width'], 'height': video['height'],
               'frame_rate': float(rate[0]) / float(rate[1]) if float(rate[-1]) else None,
               'video_codec': video.get('codec_name'), 'audio_present': audio is not None,
               'audio_codec': audio.get('codec_name') if audio else None,
               'audio_sample_rate': int(audio['sample_rate']) if audio and audio.get('sample_rate') else None,
               'file_size_bytes': path.stat().st_size, 'mean_volume_db': None,
               'silence_percentage': None, 'silence_threshold_db': -40, 'silence_minimum_seconds': .1}
    if audio:
        loud = process(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-map', '0:a:0',
                        '-af', 'volumedetect,silencedetect=noise=-40dB:d=0.1', '-f', 'null', '-']).stderr
        mean = re.search(r'mean_volume:\s*(-?[\d.]+|-inf) dB', loud)
        metrics['mean_volume_db'] = float(mean[1]) if mean and mean[1] != '-inf' else None
        audio_duration = float(audio.get('duration') or duration)
        silent = sum(float(v) for v in re.findall(r'silence_duration:\s*([\d.]+)', loud))
        metrics['silence_percentage'] = min(100., 100 * silent / audio_duration) if audio_duration else None
    sheet = path.with_suffix('.jpg')
    process(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(path), '-an',
             '-vf', f'fps={6 / max(duration, .01)},scale=180:-2,tile=6x1', '-frames:v', '1', str(sheet)])
    if not sheet.exists():
        raise Blocked('FFmpeg did not produce a contact sheet')
    metrics['contact_sheet'] = str(sheet.parent.name + '/' + sheet.name)
    metrics['portrait_9_16'] = abs(video['width'] / video['height'] - 9 / 16) < .02
    return metrics


def analyze(root):
    state = read_state(root)
    for job in state['jobs'].values():
        if job.get('file'):
            try:
                job['technical'] = analyze_video(root / 'results' / job['file'])
                job.pop('analysis_error', None)
            except (Blocked, subprocess.TimeoutExpired) as exc:
                job['analysis_error'] = str(exc) if isinstance(exc, Blocked) else 'FFmpeg analysis timed out'
    save_state(root, state)


def write_csv(path, rows, columns):
    with path.open('w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def render(root, config, prompts):
    folder = root / 'results'
    folder.mkdir(exist_ok=True)
    state = read_state(root)
    rows = []
    # Do not publish temporary signed CDN URLs or request internals.
    for job in plan(config, prompts):
        saved = state['jobs'].get(job['key'], {})
        public = {k: v for k, v in saved.items() if k not in {'task_id', 'result_url', 'request_sha256'}}
        row = dict(job, **public)
        metrics = row.get('technical')
        row['requirement_issues'] = []
        if metrics:
            if not metrics['audio_present']:
                row['requirement_issues'].append('Native output has no audio stream')
            if not metrics['portrait_9_16']:
                row['requirement_issues'].append('Output is not approximately 9:16 portrait')
        row['technical_validation_passed'] = bool(metrics) and not row['requirement_issues']
        rows.append(row)
    original_keys = {j['key'] for j in rows}
    additional = [{k: v for k, v in j.items() if k not in {'task_id', 'result_url', 'request_sha256'}}
                  for key, j in state['jobs'].items() if key not in original_keys]
    charges = [money(j['actual_cost_usd']) for j in state['jobs'].values() if j.get('actual_cost_usd') is not None]
    started = len(state['jobs'])
    complete = sum(j['status'] == 'completed' for j in rows)
    checks = state.get('account_checks', [])
    result = {'generated_at': now(), 'benchmark_complete': complete == 8 and all(j['technical_validation_passed'] for j in rows),
              'requested_jobs': 8, 'submitted_or_uncertain': started, 'completed_jobs': complete,
              'authorized_limit_usd': str(total_authorized(state)), 'safety_multiplier': str(MARGIN),
              'conservative_committed_usd': str(used_budget(state)),
              'known_actual_cost_usd': str(sum(charges, Decimal(0))),
              'actual_cost_complete': len(charges) == started,
              'remaining_balance_usd': checks[-1]['available_usd'] if checks else None,
              'requested_estimate_usd': str(sum((money(j['estimate_usd']) for j in rows if j.get('estimate_usd') is not None), Decimal(0))),
              'requested_estimate_complete': all(j.get('estimate_usd') is not None for j in rows),
              'blockers': state.get('blockers', []), 'rubric_weights': WEIGHTS,
              'evaluation': 'Qualitative scores pending human review. No claim of verified lip synchronization.',
              'jobs': rows, 'additional_jobs': additional,
              'cost_scope': 'All paid jobs in the shared ledger, including separate reference-guided pilots'}
    if result['requested_estimate_complete'] and money(result['requested_estimate_usd']) * MARGIN > LIMIT:
        result['blockers'].append('All-eight displayed-price estimate exceeds $6 after the required 25% safety margin; no full-plan spending is authorized.')
    validation_file = folder / 'validation.json'
    if validation_file.exists():
        result['implementation_validation'] = json.loads(validation_file.read_text())
    atomic_json(folder / 'results.json', result)
    cost_columns = ['key', 'model_id', 'status', 'estimate_usd', 'maximum_charge_usd',
                    'maximum_reservation_usd', 'authorized_usd', 'actual_cost_usd', 'generation_elapsed_seconds', 'reason']
    write_csv(folder / 'costs.csv', rows + additional, cost_columns)
    technical = [dict(key=j['key'], status=j['status'], generation_elapsed_seconds=j.get('generation_elapsed_seconds'),
                      actual_cost_usd=j.get('actual_cost_usd'), **j.get('technical', {})) for j in rows]
    metric_columns = ['key', 'status', 'duration_seconds', 'width', 'height', 'frame_rate', 'video_codec',
                      'audio_present', 'audio_codec', 'audio_sample_rate', 'mean_volume_db',
                      'silence_percentage', 'silence_threshold_db', 'silence_minimum_seconds', 'file_size_bytes',
                      'portrait_9_16', 'generation_elapsed_seconds', 'actual_cost_usd', 'contact_sheet']
    write_csv(folder / 'technical_metrics.csv', technical, metric_columns)
    lines = ['# API Mart video benchmark', '', f'Generated: {result["generated_at"]}', '',
             f'Completed videos: {complete}/8. Paid submissions or uncertain attempts: {started}.',
             f'Known billed total: ${result["known_actual_cost_usd"]}; '
             f'billing {"complete" if result["actual_cost_complete"] else "incomplete"}.',
             f'Global conservative committed authorization (including 25% margin): ${used_budget(state)} / ${total_authorized(state)}. '
             'Additional grants remain restricted to their explicitly authorized rounds.',
             f'Remaining provider balance: {result["remaining_balance_usd"] or "unavailable"}.', '',
             f'Displayed-price estimate for all requested jobs: ${result["requested_estimate_usd"]}; '
             f'with 25% margin: ${money(result["requested_estimate_usd"]) * MARGIN}. '
             'This estimate is not a verified maximum charge or reservation.', '',
             '## Execution limitations', '']
    lines.extend('- ' + b for b in result['blockers'])
    if additional:
        lines += ['', f'Additional image-guided jobs tracked in the same spending ledger: {len(additional)}. '
                  'These do not count toward the original eight text-only clips. '
                  'See [reference pilot report](reference/report.md) and [reference comparison](reference/comparison.html). '
                  'The known billed total above includes these additional jobs.']
    lines += ['', '| Test/model | Status | Estimated USD | Billed USD | Detail |', '|---|---|---|---|---|']
    for j in rows:
        detail = j.get('reason') or j.get('analysis_error') or j.get('duration_note', '')
        lines.append(f'| {j["key"]} | {j["status"]} | {j.get("estimate_usd") or "unverified"} | {j.get("actual_cost_usd", "unavailable")} | {detail} |')
    lines += ['', '## Human assessment rubric', '', 'Score each category from 1 to 10 after watching and listening:', '']
    lines.extend(f'- {name}: {weight:.0%}' for name, weight in WEIGHTS.items())
    lines += ['', 'All qualitative scores remain pending. Inspect exact speech, lip synchronization, eye and face motion, '
              'three landings and synchronized notes, anatomy, music, effects, ambience, continuity, and native audio.',
              '', 'Technical audio metrics use FFmpeg volumedetect mean dBFS and silencedetect at -40 dB for at least '
              '0.1 seconds. They do not measure perceived quality or synchronization. Contact sheets are representative '
              'frames, not a temporal quality judgment. Generation elapsed time includes provider queue and polling latency.',
              '', 'Gemini Omni duration is variable; no duration field is assumed. Unsupported model IDs are never substituted.',
              'Budget accounting retains the full conservative reservation after failure or refund. '
              'Actual costs are populated only from documented USD billing fields; balance deltas are not treated as per-job billing.',
              '', '## Resume', '', 'From video-benchmark/: `python3 benchmark.py resume` polls existing known task IDs only; '
              '`python3 benchmark.py execute` resumes outstanding tasks before considering unsent jobs. '
              'A submission with an unknown outcome blocks all new jobs until manually reconciled with the provider. '
              'Do not delete `.runtime/state.json` to bypass this protection.']
    (folder / 'report.md').write_text('\n'.join(lines) + '\n')
    payload = json.dumps(result, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (root / 'templates/comparison.html').read_text()
    (folder / 'comparison.html').write_text(template.replace('__BENCHMARK_DATA__', payload))
    return result


def package(root):
    target = root.parent / 'video-benchmark-results.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            relative = path.relative_to(root)
            if not path.is_file() or path.is_symlink() or any(p in {'.runtime', '.venv', '__pycache__'} for p in relative.parts):
                continue
            if path.name.startswith('.env') or path.suffix in {'.zip', '.part', '.pyc'}:
                continue
            archive.write(path, Path('video-benchmark') / relative)
    return target


def fetch_docs(root, config):
    folder = root / '.runtime/docs'
    folder.mkdir(parents=True, exist_ok=True)
    sources = [config['documentation_index']] + [m['documentation_url'] for m in config['models']]
    observations = []
    for i, url in enumerate(sources):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'CodexVideoBenchmark/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(8 * 1024 * 1024)
            (folder / f'{i}.txt').write_bytes(data)
            observations.append({'url': url, 'at': now(), 'status': 'downloaded', 'sha256': hashlib.sha256(data).hexdigest()})
        except (urllib.error.URLError, TimeoutError, OSError):
            observations.append({'url': url, 'at': now(), 'status': 'blocked',
                                 'reason': 'Documentation request failed; check domain allowlist or provider availability'})
    atomic_json(folder / 'observations.json', observations, private=True)
    print(json.dumps(observations, indent=2))
    if any(o['status'] != 'downloaded' for o in observations):
        raise Blocked('Official documentation could not be fetched; no paid calls are permitted')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['dry-run', 'fetch-docs', 'preflight', 'execute', 'resume', 'analyze', 'report', 'package'])
    parser.add_argument('--poll-seconds', type=int, default=7, choices=range(5, 11), metavar='5..10')
    parser.add_argument('--timeout', type=int, default=1800, help='Per-task polling deadline in seconds')
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error('timeout must be positive')
    try:
        config, prompts = load()
        with locked(ROOT):
            state = read_state(ROOT)
            state['blockers'] = []
            if not os.environ.get('APIMART_API_KEY'):
                state['blockers'].append('APIMART_API_KEY is not injected in this running task. Apply the existing saved Network secret binding to this environment; a fresh task may be required. Do not paste or repeatedly re-add the key.')
            if api_problem(config['api']):
                state['blockers'].append(api_problem(config['api']))
            save_state(ROOT, state)
            try:
                if args.command == 'fetch-docs':
                    fetch_docs(ROOT, config)
                elif args.command in {'execute', 'resume'}:
                    # A no-cost, persisted plan is always created before possible spending.
                    render(ROOT, config, prompts)
                    run(config, prompts, ROOT, args.command == 'resume', args.poll_seconds, args.timeout)
                    analyze(ROOT)
                elif args.command == 'preflight':
                    if not os.environ.get('APIMART_API_KEY'):
                        raise Blocked('APIMART_API_KEY is unavailable; authentication could not be verified')
                    issue = api_problem(config['api'])
                    if issue:
                        raise Blocked(issue)
                    account_check(Client(os.environ['APIMART_API_KEY']), config['api'], state, ROOT)
                elif args.command == 'analyze':
                    analyze(ROOT)
            except Blocked as exc:
                state = read_state(ROOT)
                state.setdefault('blockers', []).append(str(exc))
                save_state(ROOT, state)
                render(ROOT, config, prompts)
                raise
            result = render(ROOT, config, prompts)
            if args.command == 'dry-run':
                print('NO-COST DRY RUN: no generation requests')
                for job in result['jobs']:
                    print(job['key'], job['status'], 'estimate USD:', job['estimate_usd'], 'maximum USD:', job['maximum_charge_usd'])
                print('Conservative plan USD:', sum((charge_bound(j) for j in result['jobs'] if j['status'] == 'planned'), Decimal(0)))
                print('Requested displayed-price estimate USD:', result['requested_estimate_usd'],
                      'with 25% margin:', money(result['requested_estimate_usd']) * MARGIN)
                print('Unknown prices prevent paid execution; unknown does not mean free.')
            if args.command == 'package':
                print(package(ROOT))
            else:
                print(f'Completed real videos: {result["completed_jobs"]}/8; report: {ROOT / "results/report.md"}')
        return 0
    except Blocked as exc:
        print('BLOCKED: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
