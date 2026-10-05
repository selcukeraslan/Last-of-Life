"""Günlük, ligler arası kupon seçimi."""
import json
from datetime import date
from ..config import LEAGUES
from ..db import session
from . import engine
BANKO_MIN_P=0.75; BANKO_MIN_ODDS=1.15; BANKO_MIN_TOTAL_P=0.50
SURPRISE_MIN_P=0.20; SURPRISE_MAX_P=0.62; SURPRISE_MIN_ODDS=1.55

def _odds_from_db(conn, match_id, market):
    try:
        cols={r[1] for r in conn.execute("PRAGMA table_info(matches)")}
        for col in ("iddaa_odds","odds_json","odds"):
            if col not in cols: continue
            row=conn.execute(f"SELECT {col} FROM matches WHERE id=?",(match_id,)).fetchone()
            if row and row[0]:
                data=json.loads(row[0]) if isinstance(row[0],str) else row[0]
                value=data.get(market) if isinstance(data,dict) else None
                if value is not None and float(value)>=1.01: return round(float(value),2),"iddaa"
    except Exception: pass
    try:
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "odds" in tables:
            cols={r[1] for r in conn.execute("PRAGMA table_info(odds)")}
            if {"match_id","market","odds"}<=cols:
                row=conn.execute("SELECT odds FROM odds WHERE match_id=? AND market=?",(match_id,market)).fetchone()
                if row and row[0] and float(row[0])>=1.01: return round(float(row[0]),2),"iddaa"
    except Exception: pass
    return None,"model"

def get_odds(conn, match_id, market, suggested):
    value,source=_odds_from_db(conn,match_id,market)
    return (value if value is not None else suggested),source

def _markets(prediction,conn):
    for market,item in prediction.get("markets",{}).items():
        if item.get("suggested") and item["suggested"]>=1.01:
            odds,source=get_odds(conn,prediction["id"],market,item["suggested"])
            yield {"market":market,"p":item["p"],"odds":odds,"odds_source":source,"fair":item.get("fair")}

def _match_view(p,c):
    return {"id":p["id"],"league":p["league"],"league_name":LEAGUES[p["league"]]["name"],"kickoff":p["kickoff"],"home":p["home"],"away":p["away"],**c,"model_probability":c["p"]}

def _coupon(kind,picks,note):
    import math
    total_odds = math.prod(p["odds"] for p in picks) if picks else 0
    total_probability = math.prod(p["p"] for p in picks) if picks else 0
    return {"type":kind,"picks":picks,"total_odds":round(total_odds,2),"total_probability":round(total_probability,4),"stake_note":note}

def build_coupons(target:date):
    all_predictions=[]
    with session() as conn:
        for league in LEAGUES:
            for p in engine.get_model(league).upcoming_predictions(30):
                if p["kickoff"][:10]==target.isoformat(): all_predictions.append((p,list(_markets(p,conn))))
        candidates=[]
        for p,choices in all_predictions:
            choices=[x for x in choices if x["p"]>=BANKO_MIN_P and x["odds"]>=BANKO_MIN_ODDS]
            if choices: candidates.append((p,max(choices,key=lambda x:(x["p"],x["odds"]))))
        candidates.sort(key=lambda x:(-x[1]["p"],-x[1]["odds"]))
        banko=[_match_view(p,c) for p,c in candidates[:3]]
        while len(banko)>1 and _coupon("banko",banko,"")["total_probability"]<BANKO_MIN_TOTAL_P: banko.pop()
        banko_coupon=_coupon("banko",banko,"Sadece kaybetmeyi göze alabileceğiniz tutarla oynayın.")
        surprise=[]; allowed={"X","2","Ü2.5","Ü3.5","KG Var","A2.5"}
        for p,choices in all_predictions:
            choices=[x for x in choices if x["market"] in allowed and SURPRISE_MIN_P<=x["p"]<=SURPRISE_MAX_P and x["odds"]>=SURPRISE_MIN_ODDS]
            if choices:
                c=dict(max(choices,key=lambda x:(x["p"]*x["odds"]-1,x["p"]*(x["odds"]**0.35))))
                c["value"]=round(c["p"]*c["odds"]-1,4); c["value_signal"]="EV" if c["odds_source"]=="iddaa" else "model-oran dengesi"; surprise.append((p,c))
        surprise.sort(key=lambda x:(x[1]["value"],x[1]["p"]*(x[1]["odds"]**0.35)),reverse=True)
        selected=[]; seen=set()
        for p,c in surprise:
            if p["id"] in seen: continue
            selected.append(_match_view(p,c)); seen.add(p["id"])
            if len(selected) >= 3 and (len(selected)==5 or _coupon("surprise",selected,"")["total_odds"]>=15): break
        # Sürpriz kupon en az üç maç şartını karşılamıyorsa kupon üretme.
        if len(selected) < 3:
            selected = []
        surprise_coupon=_coupon("surprise",selected,"Sürpriz kupon: küçük miktar kullanın; garanti değildir.")
    return {"date":target.isoformat(),"banko":banko_coupon,"surprise":surprise_coupon,"rules":{"banko_min_probability":BANKO_MIN_P,"banko_min_total_probability":BANKO_MIN_TOTAL_P,"surprise_probability_range":[SURPRISE_MIN_P,SURPRISE_MAX_P],"surprise_min_total_odds":15}}
