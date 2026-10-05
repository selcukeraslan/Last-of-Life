#!/bin/sh
# İlk çalıştırmada sanal ortamı kurar, sonra sunucuyu başlatır: http://127.0.0.1:8000
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
