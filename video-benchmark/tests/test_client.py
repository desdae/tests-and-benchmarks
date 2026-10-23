import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from helpers import b, fixture, prepare, FakeClient


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(json.dumps(item).encode())


class ClientTests(unittest.TestCase):
    def test_missing_key_stops(self):
        with self.assertRaises(b.Blocked):
            b.Client('')

    def test_read_retries_transient_failure(self):
        opener = Opener([urllib.error.URLError('timeout'), {'ok': True}])
        client = b.Client('SECRET', opener=opener, sleep=lambda _: None)
        self.assertEqual(client.request('GET', '/v1/test'), {'ok': True})
        self.assertEqual(len(opener.calls), 2)

    def test_paid_post_never_retries_or_leaks_errors(self):
        for error in [urllib.error.URLError('SECRET'),
                      urllib.error.HTTPError('https://api.apimart.ai/v1/test', 429, 'SECRET', {}, None),
                      urllib.error.HTTPError('https://api.apimart.ai/v1/test', 500, 'SECRET', {}, None)]:
            opener = Opener([error, {'ok': True}])
            with self.assertRaises(b.Blocked) as caught:
                b.Client('SECRET', opener=opener).request('POST', '/v1/test', {})
            self.assertNotIn('SECRET', str(caught.exception))
            self.assertEqual(len(opener.calls), 1)

    def test_auth_and_credit_errors_are_not_retried(self):
        for code in [401, 402, 403]:
            opener = Opener([urllib.error.HTTPError('https://api.apimart.ai', code, 'private body', {}, None)])
            with self.assertRaises(b.Blocked):
                b.Client('SECRET', opener=opener).request('GET', '/v1/test')
            self.assertEqual(len(opener.calls), 1)

    def test_foreign_api_paths_are_rejected_before_transport(self):
        opener = Opener([])
        for path in ['https://attacker.example/v1/test', '//attacker.example', '/v1/../outside']:
            with self.assertRaises(b.Blocked):
                b.Client('SECRET', opener=opener).request('GET', path)
        self.assertEqual(opener.calls, [])

    def test_cdn_never_receives_authorization(self):
        opener = Opener([])
        def open_media(request, timeout):
            opener.calls.append(request)
            return io.BytesIO(b'fixture media')
        opener.open = open_media
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.urllib.request, 'build_opener', return_value=opener):
            b.download('https://cdn.example.com/video.mp4?signature=private', Path(tmp) / 'clip.mp4')
        self.assertIsNone(opener.calls[0].get_header('Authorization'))

    def test_documented_balance_conversion_and_usage_throttle(self):
        config, _ = b.load()
        class Account:
            usage_calls = 0
            def request(self, method, path):
                if path == '/v1/balance':
                    return {'success': True, 'remain_credits': 8, 'unlimited_quota': False}
                if path == '/v1/user/balance':
                    return {'success': True, 'remain_credits': 100}
                self.usage_calls += 1
                return {'success': True, 'data': {'total': {'amount_usd': 2.3}}}
        account = Account()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            state = b.read_state(root)
            self.assertEqual(b.account_check(account, config['api'], state, root), '0.8')
            self.assertEqual(b.account_check(account, config['api'], state, root), '0.8')
            self.assertEqual(account.usage_calls, 1)
            self.assertEqual(state['account_checks'][-1]['usage'], '2.3')

    def test_http_200_unsuccessful_auth_probe_stops(self):
        config, _ = b.load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            account = type('Account', (), {'request': lambda *args: {'success': False}})()
            with self.assertRaisesRegex(b.Blocked, 'unsuccessful'):
                b.account_check(account, config['api'], b.read_state(root), root)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        FakeClient.posts = 0
        FakeClient.calls = []

    def test_eight_sequential_jobs_and_rerun_does_not_resubmit(self):
        config, prompts = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            def media(url, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'fixture media')
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient), patch.object(b, 'download', side_effect=media):
                b.run(config, prompts, root)
                self.assertEqual(FakeClient.posts, 8)
                b.run(config, prompts, root)
                self.assertEqual(FakeClient.posts, 8)
            state = b.read_state(root)
            self.assertEqual(len(state['jobs']), 8)
            self.assertTrue(all(j['status'] == 'completed' for j in state['jobs'].values()))
            self.assertEqual(b.used_budget(state), b.Decimal('5.0000'))
            self.assertEqual((root / '.runtime/state.json').stat().st_mode & 0o777, 0o600)
            result = b.render(root, config, prompts)
            self.assertNotIn('result_url', (root / 'results/results.json').read_text())
            self.assertEqual(result['known_actual_cost_usd'], '3.2')
            self.assertNotIn('TEST_ONLY', (root / '.runtime/state.json').read_text())

    def test_ambiguous_post_persists_intent_and_blocks_new_requests(self):
        config, prompts = fixture()
        class Broken(FakeClient):
            def request(self, method, path, payload=None):
                if method == 'POST':
                    persisted = b.read_state(root)
                    self_test.assertEqual(next(iter(persisted['jobs'].values()))['status'], 'submitting')
                    raise b.Blocked('transport timeout')
                return super().request(method, path, payload)
        self_test = self
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', Broken):
                with self.assertRaises(b.Blocked):
                    b.run(config, prompts, root)
                state = b.read_state(root)
                self.assertEqual(next(iter(state['jobs'].values()))['status'], 'submission_unknown')
                with self.assertRaisesRegex(b.Blocked, 'unknown outcome'):
                    b.run(config, prompts, root)

    def test_resume_never_submits(self):
        config, prompts = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient):
                b.run(config, prompts, root, resume_only=True)
            self.assertEqual(FakeClient.posts, 0)

    def test_known_task_recovers_after_cdn_block_without_resubmission(self):
        config, prompts = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient):
                with patch.object(b, 'download', side_effect=b.Blocked('allow cdn.example.com')):
                    with self.assertRaisesRegex(b.Blocked, 'cdn.example.com'):
                        b.run(config, prompts, root)
                state = b.read_state(root)
                job = next(iter(state['jobs'].values()))
                self.assertEqual(job['status'], 'download_pending')
                self.assertTrue(job['task_id'])
                self.assertTrue(job['result_url'])
                with patch.object(b, 'download'):
                    b.run(config, prompts, root, resume_only=True)
                self.assertEqual(FakeClient.posts, 1)
