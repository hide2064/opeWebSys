from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import MeasurementResult

router = APIRouter()


class ResultResponse(BaseModel):
    id: int
    setting_id: int
    measurement_type: str
    timestamp: datetime
    status: str
    tx_power: Optional[float]
    evm: Optional[float]
    frequency_error: Optional[float]
    bler: Optional[float]
    raw_data: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[ResultResponse])
def list_results(
    limit: int = Query(default=50, le=200),
    setting_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(MeasurementResult)
    if setting_id:
        q = q.filter(MeasurementResult.setting_id == setting_id)
    return q.order_by(MeasurementResult.timestamp.desc()).limit(limit).all()


@router.get("/{result_id}", response_model=ResultResponse)
def get_result(result_id: int, db: Session = Depends(get_db)):
    result = db.query(MeasurementResult).filter(MeasurementResult.id == result_id).first()
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="結果が見つかりません")
    return result
