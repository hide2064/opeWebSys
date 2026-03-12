"""
pytest 共通フィクスチャ
- MySQL の代わりに SQLite (in-memory) を使用
- MT8821C TCP 接続はモック
"""
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# StaticPool: すべての接続が同一の in-memory DB を共有する
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def reset_db():
    """各テスト前にテーブルを再作成し、テスト後に削除する"""
    from db.database import Base
    import db.models  # noqa: F401 — モデル登録
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db():
    """テスト用 DB セッション"""
    session = _TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """
    FastAPI TestClient。
    - get_db を SQLite セッションで上書き
    - lifespan の create_tables を no-op に差し替え
    """
    from main import app
    from db.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with patch("main.create_tables"):           # MySQL 接続を回避
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()
