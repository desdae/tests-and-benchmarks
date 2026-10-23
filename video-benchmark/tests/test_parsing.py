import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from helpers import b, prepare


class ParsingTests(unittest.TestCase):
    def test_nested_response_and_array_indices(self):
        self.assertEqual(b.pointer({'data': [{'task_id': 'abc'}]}, '/data/0/task_id'), 'abc')
        self.assertEqual(b.pointer({'a/b': {'~': 3}}, '/a~1b/~0'), 3)

    def test_official_documented_response_mappings(self):
        config, _ = b.load()
        api = config['api']
        submitted = {'code': 200, 'data': [{'status': 'submitted', 'task_id': 'documented-shape'}]}
        completed = {'code': 200, 'data': {'status': 'completed', 'cost': .31,
            'result': {'videos': [{'url': ['https://cdn.example.com/clip.mp4']}]}}}
        self.assertEqual(b.pointer(submitted, api['submission_task_id_pointer']), 'documented-shape')
        self.assertEqual(b.pointer(completed, api['task_status_pointer']), 'completed')
        self.assertEqual(b.pointer(completed, api['video_url_pointer']), 'https://cdn.example.com/clip.mp4')
        self.assertEqual(b.pointer(completed, api['actual_cost_pointer']), .31)

    def test_missing_field_stops_instead_of_inventing_value(self):
        with self.assertRaises(b.Blocked):
            b.pointer({'data': []}, '/data/0/id')

    def test_private_state_excluded_from_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'video-benchmark'
            root.mkdir()
            prepare(root)
            (root / '.runtime/state.json').write_text('PRIVATE_SIGNED_URL')
            (root / '.env').write_text('SECRET')
            (root / 'results/report.md').write_text('public report')
            path = b.package(root)
            with b.zipfile.ZipFile(path) as archive:
                self.assertTrue(any(name.endswith('report.md') for name in archive.namelist()))
                self.assertFalse(any('.runtime' in name or '.env' in name for name in archive.namelist()))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg unavailable')
    def test_real_media_analysis_detects_silent_and_audible_audio(self):
        # Synthetic fixture solely validates technical extraction, not model quality.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=180x320:rate=12:duration=1',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000:duration=1',
                            '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', str(path)], check=True, capture_output=True)
            metrics = b.analyze_video(path)
            self.assertEqual((metrics['width'], metrics['height']), (180, 320))
            self.assertTrue(metrics['audio_present'])
            self.assertEqual(metrics['audio_sample_rate'], 24000)
            self.assertIsNotNone(metrics['mean_volume_db'])
            self.assertEqual(metrics['silence_percentage'], 0)
            self.assertTrue(path.with_suffix('.jpg').exists())
            silent_path = Path(tmp) / 'silence.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=size=180x320:rate=12:duration=1',
                            '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '1',
                            '-c:v', 'mpeg4', '-c:a', 'aac', str(silent_path)], check=True, capture_output=True)
            silent = b.analyze_video(silent_path)
            self.assertGreater(silent['silence_percentage'], 99)
            # volumedetect quantizes to 16 bits and reports a finite noise floor
            # for exact digital silence; silence detection is the relevant metric.
            self.assertLess(silent['mean_volume_db'], -80)
            no_audio_path = Path(tmp) / 'no-audio.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-c:v', 'copy', '-an', str(no_audio_path)], check=True, capture_output=True)
            no_audio = b.analyze_video(no_audio_path)
            self.assertFalse(no_audio['audio_present'])
            self.assertIsNone(no_audio['silence_percentage'])

    def test_prompt_text_is_preserved(self):
        _, prompts = b.load()
        self.assertIn("'Today is your day. Make it count!'", prompts['speech'])
        self.assertIn('Each of the three landings', prompts['music'])


if __name__ == '__main__':
    unittest.main()
