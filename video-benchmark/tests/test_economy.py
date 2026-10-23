import unittest
import economy_tests as e
import benchmark as b

class EconomySafety(unittest.TestCase):
    def test_audio_and_first_frame_contract(self):
        for slug,model in e.MODELS.items():
            p=e.payload({'slug':slug,'model_id':model,'prompt':'fixture'},'https://example.com/ref.png')
            self.assertEqual(p['duration'],6)
            self.assertTrue(p['audio'])
            self.assertEqual(p['image_urls'],['https://example.com/ref.png'])
            self.assertNotIn('first_frame_image',p) # PixVerse interprets that as transition mode.
            self.assertEqual(p['resolution'],'720p')
    def test_round_and_global_caps(self):
        state={'jobs':{'economy_round3/speech/wan_flash':{'authorized_usd':'0.315'},'old':{'authorized_usd':'7.882375'}}}
        e.ensure(state,b.Decimal('1.065'))
        with self.assertRaises(b.Blocked):e.ensure(state,b.Decimal('1.066'))
        state['jobs']['old']['authorized_usd']='11.6'
        with self.assertRaises(b.Blocked):e.ensure(state,b.Decimal('0.1'))
    def test_missing_ledger_with_round_results_blocks(self):
        import tempfile,json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'results/economy_round3/results.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'submitted_or_uncertain':1}))
            with self.assertRaises(b.Blocked):b.read_state(root)
