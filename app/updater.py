"""Veri güncelleme.

İki yol vardır ve ikisi de `meta` tablosundaki kilidi (update_lock) paylaşır:
  * run_quick_update(): web isteği içinde çalışan hızlı artımlı güncelleme (iddaa oranları + ESPN son
    günler). Serverless uyumlu: arka plan thread'i yok, son güncellemeden sonra COOLDOWN_MINUTES bekleme var.
  * run_update(): ağır tam güncelleme (tüm ligler + haberler). Komut satırı / GitHub Actions cron'u:
        python -m app.updater [--no-news] [--league tur.1]

Herkes `last_updated_at` değerini okur ("X dk önce güncellendi").
"""
import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from datetime import datetime, timedelta, timezone

from .config import LEAGUES
from .db import get_meta, init_db, session, set_meta
from .model.ratings import parse_ts
from .scrapers import espn, iddaa, news, tff

COOLDOWN_MINUTES = 10  # herkese açık sitede iki güncelleme arası en az bekleme
QUICK_LOCK_MINUTES = 3  # hızlı güncelleme kilidi zaman aşımı (çöken istek kilidi kalıcı bırakmasın)
FULL_LOCK_MINUTES = 45  # tam güncelleme kilidi zaman aşımı
RECENT_DAYS_BACK = 3  # hızlı güncellemede ESPN'den geriye bakılan gün
IDDAA_MAX_STALE_HOURS = 6  # iddaa erişilemezse eski oranlar en çok bu kadar süre gösterilir
# Serverless istek süresi (300 sn) bütçesi: hızlı güncellemede lig çekimleri en çok bu kadar bekler; ardından
# iddaa (en kötü ~55 sn) çalışır. Yavaş kalan lig atlanır, bir sonraki güncelleme tamamlar.
QUICK_MAX_WORKERS = 8
QUICK_LEAGUES_DEADLINE_SEC = 120
QUICK_IDDAA_RETRIES = 1  # hızlı endpoint bülten denemesini sınırlar; tam cron daha dayanıklıdır

_progress_state = {"message": ""}


def source_for(league: str):
    """Ligin veri kaynağı modülü (espn | tff); ikisi de sync_league / sync_recent sunar."""
    return tff if LEAGUES[league].get("source") == "tff" else espn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _progress(msg: str):
    _progress_state["message"] = msg
    print(msg, flush=True)


# --- Kilit ---------------------------------------------------------------------
def acquire_lock(conn, minutes: int) -> bool:
    """Atomik kilit alır. Değer kilidin bitiş zamanıdır; süresi geçmiş kilit tekrar alınabilir."""
    now = _now()
    cur = conn.execute(
        "INSERT INTO meta(key, value) VALUES('update_lock', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value "
        "WHERE meta.value IS NULL OR meta.value = '' OR meta.value < ?",
        (_iso(now + timedelta(minutes=minutes)), _iso(now)),
    )
    return cur.rowcount == 1


def release_lock(conn):
    set_meta(conn, "update_lock", "")


def _lock_active(conn) -> bool:
    value = get_meta(conn, "update_lock", "")
    return bool(value) and value >= _iso(_now())


def _take_lock(minutes: int, wait_seconds: int = 0) -> bool:
    deadline = time.monotonic() + wait_seconds
    while True:
        with session() as conn:
            if acquire_lock(conn, minutes):
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(3)


# --- Durum ---------------------------------------------------------------------
def cooldown_left(last_updated_at: str | None) -> int:
    """Bir sonraki güncellemeye kalan saniye (0 = şimdi güncellenebilir)."""
    if not last_updated_at:
        return 0
    elapsed = (_now() - parse_ts(last_updated_at)).total_seconds()
    return max(0, int(COOLDOWN_MINUTES * 60 - elapsed + 0.999))


def status() -> dict:
    """Herkes için ortak durum (veritabanından okunur; sunucu örneğine bağlı değildir)."""
    with session() as conn:
        last = get_meta(conn, "last_updated_at") or get_meta(conn, "last_update")
        running = _lock_active(conn)
        error = get_meta(conn, "update_last_error") or None
    return {"running": running, "last_updated_at": last, "error": error,
            "cooldown_seconds": cooldown_left(last), "cooldown_minutes": COOLDOWN_MINUTES,
            "message": _progress_state["message"] if running else ""}


# --- iddaa adımı (hızlı ve tam güncelleme ortak) ----------------------------------
def _sync_iddaa(conn, retries: int = 3) -> bool:
    try:
        iddaa.sync_odds(conn, progress=_progress, retries=retries)
        return True
    except Exception as exc:
        conn.rollback()
        set_meta(conn, "iddaa_last_error", str(exc))
        last = get_meta(conn, "iddaa_last_update")
        stale = not last or _now() - parse_ts(last) > timedelta(hours=IDDAA_MAX_STALE_HOURS)
        if stale:
            # Çok eski oranı güncelmiş gibi göstermemek için temizle; yakın tarihli oran tutulur.
            conn.execute("DELETE FROM iddaa_odds")
            conn.execute("DELETE FROM iddaa_events")
            set_meta(conn, "iddaa_stats", "null")
        conn.commit()
        _progress(f"iddaa.com oranları alınamadı ({exc}); "
                  + ("model oranları kullanılacak" if stale else "son alınan oranlar korunuyor"))
        return False


def _finish(conn, error: str | None):
    set_meta(conn, "update_last_error", error or "")
    if error is None:
        set_meta(conn, "last_updated_at", _iso(_now()))
    release_lock(conn)


def _invalidate_models():
    from .model import engine
    engine.invalidate()


def _track_coupons(freeze: bool):
    """Kupon geçmişi: (tam güncellemede) bugünün kuponunu dondurur, biten maçlara göre işaretler.
    Hata güncellemeyi bozmaz."""
    try:
        from .model import coupon_history
        if freeze:
            saved = coupon_history.freeze_today()
            if saved:
                _progress(f"Kupon geçmişine kaydedildi: {', '.join(saved)}")
        with session() as conn:
            done = coupon_history.settle(conn)
        if done["picks"]:
            _progress(f"Kupon sonuçları: {done['picks']} seçim, {done['coupons']} kupon sonuçlandı")
    except Exception as exc:
        _progress(f"Kupon geçmişi güncellenemedi: {exc}")


# --- Hızlı güncelleme (web isteği içinde) -----------------------------------------
def run_quick_update() -> dict:
    """Senkron, hızlı artımlı güncelleme. Dönen `status`: updated | cooldown | busy | error."""
    init_db()
    with session() as conn:
        last = get_meta(conn, "last_updated_at") or get_meta(conn, "last_update")
    wait = cooldown_left(last)
    if wait:
        return {"status": "cooldown", **status()}
    if not _take_lock(QUICK_LOCK_MINUTES):
        return {"status": "busy", **status()}
    error, skipped = None, False
    try:
        with session() as conn:  # kilidi beklerken başka biri güncellemiş olabilir
            last = get_meta(conn, "last_updated_at") or get_meta(conn, "last_update")
        skipped = cooldown_left(last) > 0
        if not skipped:
            def one(league):
                with session() as conn:
                    return source_for(league).sync_recent(conn, league, days_back=RECENT_DAYS_BACK)

            pool = ThreadPoolExecutor(max_workers=min(len(LEAGUES), QUICK_MAX_WORKERS))
            futures = [pool.submit(one, lg) for lg in LEAGUES]
            finished, _late = wait_futures(futures, timeout=QUICK_LEAGUES_DEADLINE_SEC)
            pool.shutdown(wait=False, cancel_futures=True)  # geç kalanlar kısa zaman aşımlarıyla kendiliğinden biter
            results = [f.result() for f in finished]
            with session() as conn:
                iddaa_ok = _sync_iddaa(conn, retries=QUICK_IDDAA_RETRIES)
            if not iddaa_ok and not any(ok for _, ok in results):
                error = "Kaynaklara ulaşılamadı (ESPN ve iddaa)"
    except Exception as exc:
        error = str(exc)
    finally:
        with session() as conn:
            if skipped:
                release_lock(conn)
            else:
                _finish(conn, error)
    if not skipped and error is None:
        _invalidate_models()
        _track_coupons(freeze=False)  # hızlı yol yalnız sonuçlandırır; dondurma ağır model kurar
    return {"status": "cooldown" if skipped else "error" if error else "updated", **status()}


# --- Tam güncelleme (cron / komut satırı) -----------------------------------------
def run_update(leagues=None, with_news=True, wait_lock_seconds: int = 0) -> str:
    """Ağır tam güncelleme. Dönen değer: "ok" | "error" | "skipped" (kilit alınamadı)."""
    init_db()
    if not _take_lock(FULL_LOCK_MINUTES, wait_lock_seconds):
        _progress("Başka bir güncelleme sürüyor; atlandı")
        return "skipped"
    error = None
    try:
        # Ligler paralel çekilir (her biri kendi bağlantısıyla); site başına istekler yine sıralı
        def one(lg):
            with session() as conn:
                return lg, source_for(lg).sync_league(conn, lg, _progress)

        with ThreadPoolExecutor(max_workers=6) as pool:
            for lg, n in pool.map(one, leagues or LEAGUES):
                _progress(f"{lg}: {n} maç işlendi")
        with session() as conn:
            _sync_iddaa(conn)
            if with_news:
                n = news.sync_news(conn, progress=_progress)
                _progress(f"{n} haber işlendi")
        _progress("Güncelleme tamamlandı")
    except Exception as exc:  # arayüzde göstermek için
        error = str(exc)
        _progress(f"Hata: {exc}")
    finally:
        with session() as conn:
            _finish(conn, error)
    if error is None:
        _invalidate_models()
        _track_coupons(freeze=True)
    return "error" if error else "ok"


def run_in_background(**kw) -> bool:
    """Yalnız yerel SQLite geliştirmesi için (açılışta eski veriyi tazele); serverless'ta kullanılmaz."""
    threading.Thread(target=run_update, kwargs=kw, daemon=True).start()
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Maç ve haber verilerini güncelle")
    p.add_argument("--league", action="append", choices=list(LEAGUES), help="Sadece bu lig(ler)")
    p.add_argument("--no-news", action="store_true", help="Haberleri atla")
    p.add_argument("--wait-lock", type=int, default=120, help="Kilit doluysa en çok kaç sn beklensin")
    a = p.parse_args()
    sys.exit(1 if run_update(a.league, with_news=not a.no_news, wait_lock_seconds=a.wait_lock) == "error" else 0)
