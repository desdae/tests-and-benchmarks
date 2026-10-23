import unittest
import shepherd_video as s
import caption_shepherd as c
import benchmark as b
class ShepherdSafety(unittest.TestCase):
 def test_requested_15s_is_not_transition_mode(self):
  p=s.payload({'prompt':'fixture'},'https://example.com/ref.png')
  self.assertEqual(p['duration'],15);self.assertTrue(p['audio']);self.assertEqual(p['resolution'],'1080p')
  self.assertNotIn('first_frame_image',p);self.assertNotIn('last_frame_image',p)
 def test_shared_budget_preserves_reservations(self):
  state={'jobs':{'old':{'authorized_usd':'9.262375'}}}
  s.ensure(state,b.Decimal('1.875'),'4.07208')
  with self.assertRaises(b.Blocked):s.ensure(state,b.Decimal('1.876'),'4.07208')
  state['jobs']['old']['authorized_usd']='11'
  with self.assertRaises(b.Blocked):s.ensure(state,b.Decimal('1.875'),'4.07208')
 def test_caption_highlight_follows_words_and_gaps(self):
  ass,e=c.build_ass([dict(word='Panic',start=.1,end=.5),dict(word='scatters',start=.7,end=1),dict(word='the',start=1,end=1.2),dict(word='flock.',start=1.2,end=1.6)])
  self.assertEqual([x['active_word'] for x in e],['Panic',None,'scatters','the','flock.'])
  self.assertTrue(all(a['end']<=z['start'] for a,z in zip(e,e[1:])))
  self.assertIn('PlayResX: 1920',ass);self.assertIn('{\\c&H0000FFFF&}Panic',ass)
  self.assertNotIn('None',ass)

 def test_missing_private_ledger_blocks_downloaded_bundle_regeneration(self):
  import tempfile,json
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'results/shepherd_round4/results.json';p.parent.mkdir(parents=True)
   p.write_text(json.dumps({'completed_jobs':1}))
   with self.assertRaises(b.Blocked):b.read_state(root)
