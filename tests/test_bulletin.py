import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import db
from app.bulletin_api import build_bulletin
from app.scrapers import iddaa
from datetime import date


class DailyBulletinTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        for p in (patch.object(db,'DB_PATH',Path(temp.name)/'db.sqlite'),patch.object(db,'DATABASE_URL',None)):
            p.start();self.addCleanup(p.stop)
        db.init_db()

    def event(self,mid,league,kickoff,small=False):
        with db.session() as c:
            c.execute('INSERT INTO iddaa_events(id,league,competition_id,kickoff,home,away,league_name,country,is_small,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (mid,league,584,kickoff,'Home','Away',league,'TR',int(small),'2026-10-24T19:00:00+00:00'))
            c.executemany('INSERT INTO iddaa_odds(event_id,market,odd) VALUES(?,?,?)',[(mid,'1',1.8),(mid,'X',3.4),(mid,'2',4.0)])

    def test_istanbul_day_order_and_unmatched_main_events_remain_visible(self):
        for args in [('de','ger.1','2026-10-25T17:00:00+00:00'),('en','eng.1','2026-10-25T18:00:00+00:00'),
                     ('tr','tur.1','2026-10-24T21:01:00+00:00'),('before','tur.1','2026-10-24T20:59:00+00:00'),
                     ('tomorrow','tur.1','2026-10-25T21:00:00+00:00')]:self.event(*args)
        result=build_bulletin(date(2026,10,25),'main')
        self.assertEqual([g['league'] for g in result['groups']],['tur.1','eng.1','ger.1'])
        self.assertEqual((result['total'],result['modeled'],result['limited']),(3,0,3))
        first=result['groups'][0]['matches'][0]
        self.assertEqual(first['id'],'iddaa:tr')
        self.assertEqual(first['iddaa_odds']['1'],1.8)
        self.assertEqual(build_bulletin(date(2026,10,26),'main')['total'],1)
        self.assertEqual(build_bulletin(date(2026,10,25),'main','eng.1')['total'],1)

    def test_other_leagues_are_combined_for_the_selected_day(self):
        self.event('a','small:one:league','2026-10-25T13:00:00+00:00',True)
        self.event('b','small:two:league','2026-10-25T16:00:00+00:00',True)
        self.event('main','tur.1','2026-10-25T17:00:00+00:00')
        result=build_bulletin(date(2026,10,25),'other')
        self.assertEqual((result['total'],len(result['groups'])),(2,2))
        self.assertTrue(all(m['id'].startswith('iddaa:') for g in result['groups'] for m in g['matches']))
        from app.main import match
        detail=match('iddaa:a')
        self.assertEqual(detail['id'],'iddaa:a')
        self.assertEqual(detail['iddaa_odds']['2'],4.0)

    def test_source_event_alias_resolves_a_later_confirmed_result(self):
        self.event('source','tur.1','2026-10-25T17:00:00+00:00')
        with db.session() as c:
            c.execute("INSERT INTO matches(id,league,kickoff,home,away,completed,home_goals,away_goals) VALUES('final','tur.1','2026-10-25T17:00:00+00:00','H','A',1,0,0)")
            c.execute("UPDATE iddaa_events SET match_id='final' WHERE id='source'")
        from app.results_api import results
        item=results(['iddaa:source'])['matches']['iddaa:source']
        self.assertEqual((item['id'],item['state'],item['home_goals']),('iddaa:source','post',0))

    def test_empty_or_diff_source_cannot_erase_the_last_valid_bulletin(self):
        self.event('keep','tur.1','2026-10-25T17:00:00+00:00')
        for payload in ({'data':{'events':[]}}, {'data':{'isdiff':True,'events':[]}}):
            with patch.object(iddaa,'fetch_json',return_value=payload), db.session() as c:
                with self.assertRaises(RuntimeError): iddaa.sync_odds(c)
                self.assertEqual(c.execute('SELECT COUNT(*) n FROM iddaa_events').fetchone()['n'],1)



class FullOddsDetailTest(unittest.TestCase):
    def test_detail_adds_missing_markets_but_does_not_replace_a_newer_price(self):
        summary={'i':1,'ci':584,'d':1,'m':[{'i':10,'v':3,'t':1,'st':1,'s':1,'o':[{'no':1,'odd':1.80,'wodd':1.7}]}]}
        detail={'data':{'i':1,'m':[
            {'i':10,'v':2,'t':1,'st':1,'s':1,'o':[{'no':1,'odd':1.9}]},
            {'i':11,'v':2,'t':2,'st':60,'s':1,'sov':'1.5','o':[{'no':1,'odd':1.7},{'no':2,'odd':2}]}]}}
        with patch.object(iddaa,'fetch_json',return_value=detail):stats=iddaa.enrich_events([summary])
        odds=iddaa._market_odds(summary['m'])
        self.assertEqual((odds['1'],odds['İY A1.5']),(1.8,1.7))
        self.assertEqual(stats['detail_loaded'],1)

    def test_source_market_minimum_is_parsed(self):
        raw={'i':1,'ci':584,'d':1793000000,'hn':'A','an':'B','mbc':3,
             'm':[{'i':10,'t':1,'st':1,'s':1,'mbc':2,'o':[{'no':1,'odd':1.8}]}]}
        self.assertEqual(iddaa.parse_event(raw)['min_matches'],{'1':2})

    def test_failed_detail_keeps_valid_summary_odds(self):
        summary={'i':1,'ci':584,'d':1,'m':[{'i':10,'v':3,'t':1,'st':1,'s':1,'o':[{'no':1,'odd':1.8}]}]}
        with patch.object(iddaa,'fetch_json',side_effect=TimeoutError):stats=iddaa.enrich_events([summary])
        self.assertEqual(iddaa._market_odds(summary['m']),{'1':1.8})
        self.assertEqual(stats['detail_failed'],1)
