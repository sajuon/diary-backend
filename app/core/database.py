from app.core.config import settings


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _get_connect_args(db_url: str) -> dict:
    # SQLite 로컬 개발 시 필요
    if db_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_get_connect_args(settings.DATABASE_URL),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()