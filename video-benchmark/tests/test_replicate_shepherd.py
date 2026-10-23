import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
import replicate_shepherd as r
import benchmark as b
class ReplicateShepherdSafety(unittest.TestCase):
 def test_provider_parameters_preserve_same_prompt_and_reference(self):
  cfg={'prompt':'exact original prompt'};p=r.payload(cfg,'https://example.com/same.png')['input']
  self.assertEqual(p['prompt'],cfg['prompt']);self.assertEqual(p['duration'],15)
  self.assertEqual(p['quality'],'1080p');self.assertTrue(p['generate_audio_switch'])
  self.assertEqual(p['image'],'https://example.com/same.png');self.assertNotIn('last_frame_image',p)
 def test_credentials_cannot_be_forwarded_to_result_host(self):
  with self.assertRaises(b.Blocked):r.Client().request('GET','https://replicate.delivery/result.mp4')
 def test_missing_replicate_private_state_blocks_public_bundle_regeneration(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'results'/r.ROUND/'results.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'completed_jobs':1}))
   with patch.object(r,'ROOT',root),patch.object(r,'STATE',root/'.runtime/replicate-state.json'):
    with self.assertRaises(b.Blocked):r.state()
 def test_quote_uses_audio_tier_and_25percent_margin(self):
  q=dict(model_id='pixverse/pixverse-v6',quality='1080p',audio=True,billing_type='output_second',verified_at=b.now(),usd_per_second='0.23')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'results'/r.ROUND/'pricing.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(q))
   with patch.object(r,'ROOT',root):
    _,estimate,bound=r.quote();self.assertEqual(estimate,b.Decimal('3.45'));self.assertEqual(bound,b.Decimal('4.3125'))
    q['usd_per_second']='0.5';p.write_text(json.dumps(q))
    with self.assertRaises(b.Blocked):r.quote()
