import math
import unittest
from app.model import predict as P, blend


class BalancedPolicyTest(unittest.TestCase):
    def test_low_odds_do_not_override_the_medium_price_band(self):
        markets = {'1': P.odds(.65), '1X': P.odds(.88), 'A3.5': P.odds(.93)}
        pick = P.best_pick(markets)
        self.assertEqual(pick['market'], '1')
        self.assertGreaterEqual(pick['odds'], 1.4)
        self.assertEqual(pick['odds_source'], 'model')

    def test_real_quote_limits_selection_to_available_markets(self):
        markets = {'1': P.odds(.65), '1X': P.odds(.88), 'A3.5': P.odds(.93)}
        pick = P.best_pick(markets, actual_odds={'1': 1.6, '1X': 1.12})
        self.assertEqual((pick['market'], pick['odds'], pick['policy']), ('1', 1.6, 'balanced_v2'))
        self.assertEqual(pick['odds_source'], 'iddaa')
        self.assertIsNone(P.best_pick(markets, actual_odds={'1X': float('nan')}))

    def test_single_quote_also_reselects_without_complete_blend_group(self):
        markets = P.markets(P.score_matrix(1.8, .8))['markets']
        pred = {'markets': markets, 'pick': P.best_pick(markets), 'data_quality': 1, 'data_n': 20}
        out = blend.blend_prediction(pred, {'1': 1.65})
        self.assertFalse(out['blend']['applied'])
        self.assertEqual(out['pick']['market'], '1')
        self.assertEqual(out['pick']['odds'], 1.65)
        self.assertNotIn('iddaa', [pred['pick']['odds_source']])

    def test_real_price_band_does_not_force_a_weak_or_out_of_band_pick(self):
        markets={'1':P.odds(.40),'1X':P.odds(.8),'2':P.odds(.6)}
        self.assertIsNone(P.best_pick(markets,actual_odds={'1':1.8,'1X':1.1,'2':3.0}))

    def test_invalid_values_and_unsettleable_markets_cannot_be_recommended(self):
        for bad in (True, None, math.nan, math.inf, -1, 0, 1.1):
            self.assertIsNone(P.best_pick({'1': {'p': bad, 'suggested': 1.2}}))
        for bad in (True, None, math.nan, math.inf, 1, -1):
            self.assertIsNone(P.best_pick({'1': P.odds(.8)}, actual_odds={'1': bad}))
        self.assertIsNone(P.best_pick({'İlk yarı 1': P.odds(.99)}))


class CandidateDisplayTests(unittest.TestCase):
    def test_below_threshold_candidate_is_not_promoted_to_a_strong_recommendation(self):
        from app import explain
        pred={'id':'m','home':'H','away':'A','pick':None,'markets':{'1':P.odds(.53)},'data_n':20,'data_quality':1}
        out=blend.blend_prediction(pred,{'1':1.9})
        self.assertIsNone(out['pick'])
        self.assertEqual(out['alternative']['market'],'1')
        summary=explain.summarize(out)
        self.assertEqual(summary['recommendation_label'],'Aday seçenek')
        self.assertIn('%56',summary['reason'])
        self.assertEqual(summary['odds'],1.9)
        self.assertEqual(summary['level'],0)
