import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import db, main


class ResultsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        for p in (patch.object(db,'DATABASE_URL',None),patch.object(db,'DB_PATH',Path(tmp.name)/'test.db')):
            p.start();self.addCleanup(p.stop)
        db.init_db()
        self.client=TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_final_old_match_survives_current_live_feed_and_uses_no_prediction(self):
        with db.session() as c:
            c.execute("INSERT INTO matches(id,league,kickoff,home,away,completed,home_goals,away_goals,status) "
                      "VALUES('old','eng.1','2026-01-01T18:00Z','A','B',1,0,0,'FT')")
        with patch.object(main.engine,'get_model',side_effect=AssertionError('must not build a model')):
            response=self.client.get('/api/results',params=[('ids','old'),('ids','missing')])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.json()['matches']['old']['state'],'post')
        self.assertEqual(response.json()['matches']['old']['home_goals'],0)
        self.assertEqual(response.json()['matches']['missing']['state'],'unknown')

    def test_elapsed_kickoff_without_score_is_not_zero_zero_or_final(self):
        with db.session() as c:
            c.execute("INSERT INTO matches(id,league,kickoff,home,away,completed) VALUES('pending','eng.1','2026-01-01T18:00Z','A','B',0)")
        row=self.client.get('/api/results',params={'ids':'pending'}).json()['matches']['pending']
        self.assertEqual(row['state'],'unknown')
        self.assertIsNone(row['home_goals'])

    def test_query_is_bounded_and_ids_are_parameters(self):
        self.assertEqual(self.client.get('/api/results',params=[('ids',str(i)) for i in range(31)]).status_code,422)
        unusual="a' OR 1=1 --"
        r=self.client.get('/api/results',params={'ids':unusual})
        self.assertEqual(r.status_code,200)
        self.assertEqual(list(r.json()['matches']),[unusual])
