"""
Script for checking that a database server is available.
Essentially a cross-platform, database agnostic mysqladmin.
"""
import time

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

from CTFd.config import Config

url = make_url(Config.DATABASE_URL)

# Ignore sqlite databases
if url.drivername.startswith("sqlite"):
    exit(0)

# CTFd can create a local database, so historically this check connects without
# one. Supabase's shared pooler requires the target database name to be present;
# without it PostgreSQL defaults to the pooler username (postgres.<project-ref>),
# which is not a database.
is_supabase_pooler = url.host and url.host.endswith(".pooler.supabase.com")
if not is_supabase_pooler:
    url = url._replace(database=None)

# Wait for the database server to be available
engine = create_engine(url)
print(f"Waiting for {url.host} to be ready")
while True:
    try:
        engine.raw_connection()
        break
    except Exception as e:
        print(e)
        print("Waiting 1s for database connection")
        time.sleep(1)

print(f"{url.host} is ready")
time.sleep(1)
