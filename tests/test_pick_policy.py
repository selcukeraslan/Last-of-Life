import math
import unittest
from app.model import predict as P, blend


class HitRatePolicyTest(unittest.TestCase):
    def test_low_odds_high_probability_is_not_excluded(self):
        markets = {'1': P.odds(.65), '1X': P.odds(.88), 'A3.5': P.odds(.93)}
        pick = P.best_pick(markets)
        self.assertEqual(pick['market'], 'A3.5')
        self.assertLess(pick['odds'], 1.4)
        self.assertEqual(pick['odds_source'], 'model')

    def test_real_quote_limits_selection_to_available_markets(self):
        markets = {'1': P.odds(.65), '1X': P.odds(.88), 'A3.5': P.odds(.93)}
        pick = P.best_pick(markets, actual_odds={'1': 1.6, '1X': 1.12})
        self.assertEqual((pick['market'], pick['odds'], pick['policy']), ('1X', 1.12, 'hit_rate_v1'))
        self.assertEqual(pick['odds_source'], 'iddaa')
        self.assertIsNone(P.best_pick(markets, actual_odds={'1X': float('nan')}))

    def test_single_quote_also_reselects_without_complete_blend_group(self):
        markets = P.markets(P.score_matrix(1.8, .8))['markets']
        pred = {'markets': markets, 'pick': P.best_pick(markets), 'data_quality': 1, 'data_n': 20}
        out = blend.blend_prediction(pred, {'1': 1.15})
        self.assertFalse(out['blend']['applied'])
        self.assertEqual(out['pick']['market'], '1')
        self.assertEqual(out['pick']['odds'], 1.15)
        self.assertNotEqual(pred['pick']['market'], '1')

    def test_invalid_values_and_unsettleable_markets_cannot_be_recommended(self):
        for bad in (True, None, math.nan, math.inf, -1, 0, 1.1):
            self.assertIsNone(P.best_pick({'1': {'p': bad, 'suggested': 1.2}}))
        for bad in (True, None, math.nan, math.inf, 1, -1):
            self.assertIsNone(P.best_pick({'1': P.odds(.8)}, actual_odds={'1': bad}))
        self.assertIsNone(P.best_pick({'İlk yarı 1': P.odds(.99)}))
