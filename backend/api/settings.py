from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Setting
from core.logger import get_logger

logger = get_logger("settings")

router = APIRouter()


class SettingCreate(BaseModel):
    name: str
    rat: str = "LTE"                  # LTE / WCDMA / GSM / NR5G
    duplex_mode: str = "FDD"          # FDD / TDD
    frequency: float                  # MHz (DL中心周波数)
    bandwidth: float = 10.0           # MHz
    channel_number: Optional[int] = None  # EARFCN / UARFCN / ARFCN
    power_level: float = -20.0        # 参照レベル (dBm)
    expected_power: float = -10.0     # 期待UE送信電力 (dBm)
    meas_count: int = 1               # 測定回数


class SettingResponse(BaseModel):
    id: int
    name: str
    rat: str
    duplex_mode: str
    frequency: float
    bandwidth: float
    channel_number: Optional[int]
    power_level: float
    expected_power: float
    meas_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[SettingResponse])
def list_settings(db: Session = Depends(get_db)):
    return db.query(Setting).order_by(Setting.updated_at.desc()).all()


@router.get("/{setting_id}", response_model=SettingResponse)
def get_setting(setting_id: int, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="設定が見つかりません")
    return setting


@router.post("/", response_model=SettingResponse, status_code=201)
def create_setting(body: SettingCreate, db: Session = Depends(get_db)):
    setting = Setting(**body.model_dump())
    db.add(setting)
    db.commit()
    db.refresh(setting)
    logger.info(f"設定作成: id={setting.id} name='{setting.name}' RAT={setting.rat} freq={setting.frequency}MHz")
    return setting


@router.put("/{setting_id}", response_model=SettingResponse)
def update_setting(setting_id: int, body: SettingCreate, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="設定が見つかりません")
    for key, value in body.model_dump().items():
        setattr(setting, key, value)
    db.commit()
    db.refresh(setting)
    logger.info(f"設定更新: id={setting.id} name='{setting.name}'")
    return setting


@router.delete("/{setting_id}", status_code=204)
def delete_setting(setting_id: int, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.id == setting_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="設定が見つかりません")
    logger.info(f"設定削除: id={setting.id} name='{setting.name}'")
    db.delete(setting)
    db.commit()
