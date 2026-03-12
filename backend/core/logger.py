"""
アプリケーション共通ロガー
- コンソール: INFO 以上
- ファイル  : DEBUG 以上 (RotatingFileHandler, 10MB × 5世代)
- DB       : INFO 以上 (system_logs テーブル)
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.getenv("LOG_DIR", "/logs")

_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_MSG_FORMATTER = logging.Formatter("%(message)s")

_file_handler: logging.Handler | None = None


def _get_file_handler() -> logging.Handler | None:
    global _file_handler
    if _file_handler is None:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            h = RotatingFileHandler(
                os.path.join(LOG_DIR, "app.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            h.setLevel(logging.DEBUG)
            h.setFormatter(_FORMATTER)
            _file_handler = h
        except Exception:
            pass
    return _file_handler


class _DBLogHandler(logging.Handler):
    """ログレコードを system_logs テーブルへ書き込む"""

    def emit(self, record: logging.LogRecord) -> None:
        # 循環インポートを避けるため遅延インポート
        try:
            from db.database import SessionLocal
            from db.models import SystemLog

            session = SessionLocal()
            try:
                entry = SystemLog(
                    level=record.levelname,
                    logger=record.name,
                    message=record.getMessage(),
                )
                session.add(entry)
                session.commit()
            finally:
                session.close()
        except Exception:
            pass  # DB 書き込み失敗は無視（無限ループを防ぐ）


_db_handler: _DBLogHandler | None = None


def _get_db_handler() -> _DBLogHandler:
    global _db_handler
    if _db_handler is None:
        _db_handler = _DBLogHandler()
        _db_handler.setLevel(logging.INFO)
    return _db_handler


def get_logger(name: str) -> logging.Logger:
    """アプリケーション用ロガーを取得する"""
    logger = logging.getLogger(f"opeWebSys.{name}")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # コンソール
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(_FORMATTER)
        logger.addHandler(ch)

        # ファイル
        fh = _get_file_handler()
        if fh:
            logger.addHandler(fh)

        # DB
        logger.addHandler(_get_db_handler())

    return logger
