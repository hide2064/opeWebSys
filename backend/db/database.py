import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://mt8821c_user:mt8821c_pass@localhost:3306/mt8821c_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    import time
    from db import models  # noqa: F401
    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as e:
            if attempt == 9:
                raise
            print(f"DB接続待機中... ({attempt + 1}/10): {e}")
            time.sleep(3)
