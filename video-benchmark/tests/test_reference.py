import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import b, fixture, prepare, FakeClient
import reference_tests as ref


class ReferenceTests(unittest.TestCase):
    def test_documented_first_frame_payload_and_native_audio(self):
        base = {'model_id': 'wan3.0-video', 'slug': 'wan3', 'prompt': 'Test', 'resolution': '720P'}
        p = ref.payload(base, 'https://example.com/image.png')
        self.assertEqual(p['image_urls'], ['https://example.com/image.png'])
        self.assertEqual(p['generation_type'], 'frame')
        self.assertTrue(p['audio'])
        self.assertEqual(p['duration'], 5)
        base.update(model_id='MiniMax-H3', slug='minimax_h3', resolution='768P')
        p = ref.payload(base, 'https://example.com/image.png')
        self.assertEqual(p['first_frame_image'], 'https://example.com/image.png')
        self.assertNotIn('image_urls', p)
        self.assertNotIn('audio', p)  # Native audio included; no undocumented toggle.

    def test_pilot_shares_budget_and_cannot_repeat_paid_jobs(self):
        config, _ = fixture()
        pilot = ref.settings()
        prices = {slug: {'model_id': mid, 'resolution': resolution, 'estimate_usd': '.3',
            'maximum_charge_usd': '.4', 'maximum_reservation_usd': '.4', 'checked_at': b.now()}
            for slug, (mid, resolution) in ref.SELECTED.items()}
        FakeClient.posts = 0
        FakeClient.calls = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            def download(url, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'fixture only')
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient), \
                 patch.object(b, 'download', side_effect=download), patch.object(ref, 'upload', return_value='https://example.com/ref.png'):
                ref.execute(config, pilot, prices, root)
                self.assertEqual(FakeClient.posts, 4)
                ref.execute(config, pilot, prices, root)
                ref.execute(config, pilot, prices, root, resume=True)
                self.assertEqual(FakeClient.posts, 4)
            state = b.read_state(root)
            self.assertEqual(b.used_budget(state), b.Decimal('2.0'))
            with self.assertRaises(b.Blocked):
                b.ensure_budget(state, b.Decimal('4.01'))
            public = (root / 'results/reference/results.json').read_text()
            self.assertNotIn('task_id', public)
            self.assertNotIn('result_url', public)
            combined = b.render(root, config, {'speech': 'A', 'music': 'B'})
            self.assertEqual(combined['known_actual_cost_usd'], '1.6')
            self.assertEqual(combined['completed_jobs'], 0)
            self.assertEqual(len(combined['additional_jobs']), 4)

    def test_original_run_authorization_is_not_reset_for_pilot(self):
        config, _ = fixture()
        pilot = ref.settings()
        prices = {slug: {'model_id': mid, 'resolution': resolution, 'estimate_usd': '.3',
            'maximum_charge_usd': '.4', 'maximum_reservation_usd': '.4', 'checked_at': b.now()}
            for slug, (mid, resolution) in ref.SELECTED.items()}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            state = b.read_state(root)
            state['jobs']['prior'] = {'status': 'failed', 'authorized_usd': '5'}
            b.save_state(root, state)
            FakeClient.posts = 0
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient):
                with self.assertRaises(b.Blocked):
                    ref.execute(config, pilot, prices, root)
            self.assertEqual(FakeClient.posts, 0)

    def test_cdn_deferral_keeps_completed_generation_without_resubmission(self):
        config, _ = fixture()
        pilot = ref.settings()
        prices = {slug: {'model_id': mid, 'resolution': resolution, 'estimate_usd': '.3',
            'maximum_charge_usd': '.4', 'maximum_reservation_usd': '.4', 'checked_at': b.now()}
            for slug, (mid, resolution) in ref.SELECTED.items()}
        FakeClient.posts = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient), \
                 patch.object(ref, 'upload', return_value='https://example.com/ref.png'):
                with patch.object(b, 'download', side_effect=b.Blocked('Media download failed; check HTTPS host cdn.example.com')):
                    ref.execute(config, pilot, prices, root)
                state = b.read_state(root)
                self.assertEqual(FakeClient.posts, 4)
                self.assertTrue(all(j['status'] == 'download_pending' and j.get('task_id') and j.get('result_url')
                                    for j in state['jobs'].values()))
                with patch.object(b, 'download'):
                    ref.execute(config, pilot, prices, root, resume=True)
                self.assertEqual(FakeClient.posts, 4)
                self.assertTrue(all(j['status'] == 'completed' for j in b.read_state(root)['jobs'].values()))

    def test_pending_generation_error_cannot_be_deferred_as_cdn_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            job = {'status': 'pending', 'key': 'reference/speech/wan3'}
            with patch.object(b, 'poll', side_effect=b.Blocked('Polling timed out')):
                with self.assertRaisesRegex(b.Blocked, 'Polling timed out'):
                    ref.poll_allow_cdn_deferral(None, None, job, root, b.read_state(root))

    def test_downloaded_bundle_cannot_start_a_new_ledger_over_completed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            folder = root / 'results/reference'
            folder.mkdir()
            b.atomic_json(folder / 'results.json', {'completed_jobs': 4})
            with self.assertRaisesRegex(b.Blocked, 'private spending ledger is missing'):
                b.read_state(root)
