import os

# Testler her zaman geçici SQLite kullanır; .env'deki gerçek Postgres'e asla bağlanmaz.
os.environ["DATABASE_URL"] = ""
