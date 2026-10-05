"""Veri güncelleme işlemi. Komut satırından: python -m app.updater [--no-news] [--league tur.1]"""
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .config import LEAGUES
from .db import init_db, session, set_meta
from .scrapers import espn, iddaa, news

_state = {"running": False, "message": "", "started_at": None, "finished_at": None, "error": None}
_lock = threading.Lock()


def state() -> dict:
    return dict(_state)


def _progress(msg: str):
    _state["message"] = msg
    print(msg, flush=True)


def run_update(leagues=None, with_news=True):
    with _lock:
        if _state["running"]:
            return False
        _state.update(running=True, error=None, started_at=datetime.now(timezone.utc).isoformat())
    try:
        init_db()
        # Ligler paralel çekilir (her biri kendi bağlantısıyla); site başına istekler yine sıralı
        def one(lg):
            with session() as conn:
                return lg, espn.sync_league(conn, lg, _progress)

        with ThreadPoolExecutor(max_workers=6) as pool:
            for lg, n in pool.map(one, leagues or LEAGUES):
                _progress(f"{lg}: {n} maç işlendi")
        with session() as conn:
            try:
                iddaa.sync_odds(conn, progress=_progress)
            except Exception as exc:
                # Eski oranı güncelmiş gibi göstermemek için erişim hatasında temizle.
                conn.execute("DELETE FROM iddaa_odds")
                conn.execute("DELETE FROM iddaa_events")
                set_meta(conn, "iddaa_last_error", str(exc))
                _progress(f"iddaa.com oranları alınamadı ({exc}); model oranları kullanılacak")
            if with_news:
                n = news.sync_news(conn, progress=_progress)
                _progress(f"{n} haber işlendi")
            set_meta(conn, "last_update", datetime.now(timezone.utc).isoformat())
        from .model import engine
        engine.invalidate()
        _progress("Güncelleme tamamlandı")
    except Exception as exc:  # arayüzde göstermek için
        _state["error"] = str(exc)
        _progress(f"Hata: {exc}")
    finally:
        _state.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())
    return True


def run_in_background(**kw) -> bool:
    if _state["running"]:
        return False
    threading.Thread(target=run_update, kwargs=kw, daemon=True).start()
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Maç ve haber verilerini güncelle")
    p.add_argument("--league", action="append", choices=list(LEAGUES), help="Sadece bu lig(ler)")
    p.add_argument("--no-news", action="store_true", help="Haberleri atla")
    a = p.parse_args()
    run_update(a.league, with_news=not a.no_news)
