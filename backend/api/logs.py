"""
システムログ API (/api/logs)
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import SystemLog

router = APIRouter()


class LogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    logger: str
    message: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[LogResponse])
def list_logs(
    limit: int = Query(default=200, le=1000),
    level: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """ログ一覧を新しい順で返す"""
    q = db.query(SystemLog).order_by(SystemLog.timestamp.desc())
    if level:
        q = q.filter(SystemLog.level == level.upper())
    return q.limit(limit).all()


@router.delete("/", status_code=204)
def clear_logs(db: Session = Depends(get_db)):
    """全ログを削除する"""
    db.query(SystemLog).delete()
    db.commit()
