# Canlı E2E duman testi

Playwright repoya bağımlılık olarak eklenmez. Ayrı kurun:

    mkdir /tmp/pw && cd /tmp/pw && npm i playwright && npx playwright install chromium
    NODE_PATH=/tmp/pw/node_modules node tests/e2e/live_smoke.js [url]

Masaüstü (1280) ve mobil (390) için tüm sekmeleri gezer; console/pageerror, 4xx/5xx API ve ham `Hata: {...}` metinlerini listeler. Temizse `CLEAN` yazar. Ekran görüntüleri `E2E_OUT` (varsayılan /tmp/e2e-shots).
