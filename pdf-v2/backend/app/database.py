from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# fallback to sqlite if postgres not reachable at import time; actual url is from settings
url = settings.DATABASE_URL
try:
    import psycopg2  # noqa
except ImportError:
    if url.startswith("postgresql"):
        # fallback to sqlite for local dev without postgres driver
        url = "sqlite:///./sofia.db"

if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {}
if url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def _migrate_sqlite():
    if not url.startswith("sqlite"): return
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # check users table columns
            rows=conn.execute(text("PRAGMA table_info(users)")).fetchall()
            cols={r[1] for r in rows}
            if "username" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR"))
                conn.commit()
            if "max_file_mb" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN max_file_mb INTEGER DEFAULT 100"))
                conn.commit()
            if "must_change_password" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
                conn.commit()
            if rows and "email" in cols:
                pass
            # ensure system_settings exists created by Base, nothing extra
    except Exception as e:
        print("migrate sqlite:", e)

try:
    _migrate_sqlite()
except: pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
