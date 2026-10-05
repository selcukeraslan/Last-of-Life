import unittest
from datetime import date
from unittest.mock import patch
from app.model.coupons import _coupon, build_coupons

class CouponRulesTest(unittest.TestCase):
    def test_coupon_totals_multiply(self):
        result = _coupon("banko", [{"odds": 2.0, "p": 0.8}, {"odds": 1.5, "p": 0.75}], "not")
        self.assertEqual(result["total_odds"], 3.0)
        self.assertEqual(result["total_probability"], 0.6)
    def test_no_matches_returns_empty_coupons(self):
        with patch("app.model.coupons.LEAGUES", {}): result = build_coupons(date(2026, 1, 1))
        self.assertEqual(result["banko"]["picks"], [])
        self.assertEqual(result["surprise"]["picks"], [])

if __name__ == "__main__": unittest.main()
