import importlib.util
import functools
import http.server
from pathlib import Path
import tempfile
import threading
import unittest

from helpers import b, fixture, prepare


@unittest.skipUnless(importlib.util.find_spec('playwright') and b.shutil.which('chromium'),
                     'Optional browser validation requires Playwright and Chromium')
class ViewerTests(unittest.TestCase):
    def test_local_tabs_scoring_weighted_rankings_and_export(self):
        from playwright.sync_api import sync_playwright
        config, prompts = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root)
            jobs = b.plan(config, prompts)
            # Synthetic result metadata only, never mixed into real benchmark results.
            state = b.read_state(root)
            for job in jobs:
                job.update(status='completed', file=job['key']+'.mp4', authorized_usd='.625', actual_cost_usd='.4')
                state['jobs'][job['key']] = job
            b.save_state(root, state)
            b.render(root, config, prompts)
            class QuietHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
                functools.partial(QuietHandler, directory=str(root / 'results')))
            self.addCleanup(server.server_close)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.shutdown)
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=b.shutil.which('chromium'), headless=True,
                                            args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1200, 'height': 1000})
                errors = []
                page.on('pageerror', lambda exc: errors.append(str(exc)))
                # Managed Chromium prohibits all file: navigation in this cloud.
                # Test the identical standalone HTML via an internal loopback server.
                page.goto(f'http://127.0.0.1:{server.server_port}/comparison.html')
                self.assertEqual(page.locator('.card').count(), 4)
                self.assertEqual(page.locator('video[controls]').count(), 4)
                first = page.locator('.card').first
                for field in first.locator('input[type=number]').all():
                    field.fill('8')
                self.assertIn('8.00', page.locator('#leaderboard').inner_text())
                self.assertIn('Pending', page.locator('#leaderboard tr').first.inner_text())
                page.locator('#music').click()
                for field in page.locator('.card').first.locator('input[type=number]').all():
                    field.fill('6')
                row = page.locator('#leaderboard tr').first.inner_text()
                self.assertIn('8.00', row)
                self.assertIn('6.00', row)
                self.assertIn('7.00', row)
                page.locator('#unmute').click()
                self.assertTrue(page.locator('video').evaluate_all('(vs)=>vs.every(v=>!v.muted)'))
                page.locator('#mute').click()
                self.assertTrue(page.locator('video').evaluate_all('(vs)=>vs.every(v=>v.muted)'))
                with page.expect_download() as download:
                    page.locator('#export').click()
                self.assertEqual(download.value.suggested_filename, 'benchmark-scores.json')
                page.reload()
                self.assertIn('7.00', page.locator('#leaderboard tr').first.inner_text())
                self.assertEqual(errors, [])
                browser.close()
