import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from helpers import b, fixture, prepare, FakeClient
import shorts_tests as shorts


class ShortsTests(unittest.TestCase):
    def test_new_round_budget_is_separate_but_old_reservations_are_retained(self):
        state = {'jobs': {'reference/full/a': {'authorized_usd': '1.919875'}}}
        shorts.ensure(state, b.Decimal('5.9625'), '8.77128')
        state['jobs']['shorts_round2/full/veo_quality'] = {'authorized_usd': '2'}
        shorts.ensure(state, b.Decimal('3.9625'))
        with self.assertRaises(b.Blocked):
            shorts.ensure(state, b.Decimal('4.01'))
        with self.assertRaises(b.Blocked):
            shorts.ensure({'jobs': {}}, b.Decimal('5.9625'), '5.9')

    def test_veo_price_uses_audio_inclusive_matrix_instead_of_video_only(self):
        cfg = shorts.config()
        def opened(request, timeout):
            self.assertIsNone(request.get_header('Authorization'))
            if 'veo3.1' in request.full_url:
                data = {'model_name': 'veo3.1-quality-official', 'billing_type': 'per_second',
                    'resolution_prices': {'1080P': .2}, 'resolution_paid_prices': {'1080P': .16},
                    'billing_matrix': {'1080P': {'audio': .4, 'video': .2}},
                    'billing_matrix_paid_prices': {'1080P': {'audio': .32, 'video': .16}}}
            else:
                data = {'model_name': 'kling-v4', 'billing_type': 'per_second',
                    'resolution_prices': {'720P': .19625}, 'resolution_paid_prices': {'720P': .157}}
            return io.BytesIO(json.dumps({'success': True, 'data': data}).encode())
        with patch.object(shorts.urllib.request, 'urlopen', side_effect=opened):
            quotes = shorts.prices(cfg)
        self.assertEqual(b.money(quotes['veo_quality']['estimate_usd']), b.Decimal('1.28'))
        total = sum((b.charge_bound(j) for j in shorts.jobs(cfg, quotes)), b.Decimal(0))
        self.assertEqual(total, b.Decimal('5.9625'))

    def test_native_audio_controls_and_no_undocumented_kling_audio_toggle(self):
        base = {'model_id': 'veo3.1-quality-official', 'slug': 'veo_quality', 'prompt': 'Test', 'resolution': '1080p'}
        result = shorts.payload(base, 'https://example.com/photo.png')
        self.assertTrue(result['generate_audio'])
        self.assertEqual(result['sample_count'], 1)
        self.assertEqual(result['duration'], 4)
        base.update(model_id='kling-v4', slug='kling_v4', resolution='720p')
        result = shorts.payload(base, 'https://example.com/photo.png')
        self.assertNotIn('generate_audio', result)
        self.assertNotIn('negative_prompt', result)

    def test_sequential_new_round_does_not_repeat_existing_paid_jobs(self):
        cfg = shorts.config()
        api = fixture()[0]['api']
        quotes = {slug: {'estimate_usd': '.3', 'maximum_charge_usd': '.4',
            'maximum_reservation_usd': '.4', 'price_checked_at': b.now()}
            for slug in cfg['models']}
        FakeClient.posts = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            def media(url, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'test fixture')
            with patch.dict(b.os.environ, {'APIMART_API_KEY': 'TEST_ONLY'}), patch.object(b, 'Client', FakeClient), \
                 patch.object(b, 'download', side_effect=media), patch.object(shorts.ref, 'upload', return_value='https://example.com/ref.png'):
                shorts.execute(cfg, quotes, api, root)
                shorts.execute(cfg, quotes, api, root)
                shorts.execute(cfg, quotes, api, root, resume=True)
            self.assertEqual(FakeClient.posts, 4)
            self.assertEqual(shorts.round_used(b.read_state(root)), b.Decimal('2'))

    @unittest.skipUnless(b.shutil.which('ffmpeg') and b.shutil.which('ffprobe'), 'FFmpeg unavailable')
    def test_real_export_has_exact_canvas_clear_upper_half_and_unchanged_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            original = root / 'results/shorts_round2/lower/test.mp4'
            original.parent.mkdir(parents=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=180x320:rate=12:duration=0.5',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000:duration=0.5',
                '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', str(original)], check=True, capture_output=True)
            state = b.read_state(root)
            key = 'shorts_round2/lower/test'
            state['jobs'][key] = {'status': 'completed', 'layout': 'lower', 'slug': 'test',
                'file': 'shorts_round2/lower/test.mp4', 'authorized_usd': '.5'}
            b.save_state(root, state)
            shorts.export(root)
            job = b.read_state(root)['jobs'][key]
            m = job['delivery_technical']
            self.assertEqual((m['width'], m['height']), (1080, 1920))
            self.assertLessEqual(m['upper_half_luma_range_max'], 3)
            target = root / 'results' / job['delivery_file']
            def audio_hash(path):
                raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-c', 'copy', '-f', 'adts', '-'])
                return hashlib.sha256(raw).hexdigest()
            self.assertEqual(audio_hash(original), audio_hash(target))

    def test_fresh_clone_cannot_recreate_round_two_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            b.atomic_json(root / 'results/shorts_round2/results.json', {'completed_jobs': 4})
            with self.assertRaises(b.Blocked):
                b.read_state(root)
