from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from ..core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

if _is_sqlite:
    # WAL lets readers and a single writer coexist without blocking; combined
    # with a 30s busy_timeout this prevents "database is locked" errors when
    # the API writes (e.g. project deletion) while the Celery worker is in
    # the middle of a bulk to_sql. WAL is a DB-file property that persists,
    # so setting it on every connect is idempotent and the separately-
    # running worker process picks it up too.
    @event.listens_for(engine, "connect")
    def _sqlite_set_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
