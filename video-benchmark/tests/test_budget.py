import unittest
from helpers import b, fixture


class BudgetTests(unittest.TestCase):
    def test_25_percent_margin_and_reservations(self):
        self.assertEqual(b.charge_bound({'maximum_charge_usd': '0.40', 'maximum_reservation_usd': '0.60'}), b.Decimal('.75'))

    def test_full_plan_over_budget_skips_every_paid_request(self):
        config, prompts = fixture()
        for model in config['models']:
            model.update(maximum_charge_usd='.61', maximum_reservation_usd='.61')
        jobs = b.plan(config, prompts)
        self.assertEqual(len(jobs), 8)
        self.assertTrue(all(j['status'] == 'skipped' for j in jobs))

    def test_exact_budget_boundary(self):
        state = {'jobs': {'prior': {'authorized_usd': '5.375'}}}
        b.ensure_budget(state, b.Decimal('.625'))
        with self.assertRaises(b.Blocked):
            b.ensure_budget(state, b.Decimal('.626'))

    def test_failed_job_still_consumes_authorization(self):
        state = {'jobs': {'failed': {'authorized_usd': '6', 'actual_cost_usd': '0', 'status': 'failed'}}}
        with self.assertRaises(b.Blocked):
            b.ensure_budget(state, b.Decimal('.001'))

    def test_provider_balance_must_cover_bound(self):
        with self.assertRaises(b.Blocked):
            b.ensure_budget({'jobs': {}}, b.Decimal('.625'), '.60')

    def test_unknown_unbounded_or_nonfinite_prices_are_skipped(self):
        for value in [None, 'NaN', 'Infinity', '-.1']:
            config, prompts = fixture()
            config['models'][0]['maximum_charge_usd'] = value
            jobs = [j for j in b.plan(config, prompts) if j['slug'] == 'wan3']
            self.assertTrue(all(j['status'] == 'skipped' for j in jobs))

    def test_unverified_config_never_prices_unknown_as_free(self):
        config, prompts = b.load()
        self.assertTrue(all(j['status'] == 'skipped' and j['maximum_reservation_usd'] is None for j in b.plan(config, prompts)))

    def test_expired_verification_blocks_model(self):
        config, _ = fixture()
        config['models'][0]['verified_at'] = '2020-01-01T00:00:00+00:00'
        self.assertIsNotNone(b.model_problem(config['models'][0]))

    def test_model_substitution_is_rejected(self):
        config, _ = fixture()
        config['models'][0]['model_id'] = 'different-model'
        self.assertIn('substitution', b.model_problem(config['models'][0]))
