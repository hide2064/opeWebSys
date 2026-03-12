import asyncio
import json
import os
from typing import Optional, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import MeasurementResult, Setting
from instrument.mt8821c import MT8821C, MT8821CError

router = APIRouter()
ws_router = APIRouter()

# ------------------------------------------------------------------
# グローバル計測器インスタンス
# ------------------------------------------------------------------
instrument = MT8821C(
    host=os.getenv("MT8821C_HOST", "192.168.1.100"),
    port=int(os.getenv("MT8821C_PORT", "5025")),
    timeout=float(os.getenv("MT8821C_TIMEOUT", "10")),
)


# ------------------------------------------------------------------
# WebSocket 接続マネージャ
# ------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.active.discard(ws)


manager = ConnectionManager()


# ------------------------------------------------------------------
# リクエストスキーマ
# ------------------------------------------------------------------
class ConnectRequest(BaseModel):
    host: Optional[str] = None


class MeasureRequest(BaseModel):
    setting_id: int


# ------------------------------------------------------------------
# REST エンドポイント
# ------------------------------------------------------------------
@router.get("/status")
def get_status():
    return {
        "connected": instrument.is_connected,
        "host": instrument.host,
        "port": instrument.port,
    }


@router.post("/connect")
def connect(req: Optional[ConnectRequest] = None):
    if req and req.host:
        instrument.host = req.host
    try:
        instrument.connect()
        idn = instrument.identify()
        return {"status": "connected", "identity": idn}
    except MT8821CError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/disconnect")
def disconnect():
    instrument.disconnect()
    return {"status": "disconnected"}


@router.post("/measure")
async def measure(req: MeasureRequest, db: Session = Depends(get_db)):
    if not instrument.is_connected:
        raise HTTPException(status_code=503, detail="MT8821C に接続されていません")

    setting: Optional[Setting] = db.query(Setting).filter(Setting.id == req.setting_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="設定が見つかりません")

    # ブロッキング I/O をスレッドプールで実行
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            instrument.apply_setting,
            setting.frequency,
            setting.bandwidth,
            setting.power_level,
        )
        results: dict = await loop.run_in_executor(None, instrument.measure, setting.rat)

        result = MeasurementResult(
            setting_id=setting.id,
            measurement_type=setting.rat,
            status="success",
            tx_power=results.get("tx_power"),
            evm=results.get("evm"),
            frequency_error=results.get("frequency_error"),
            bler=results.get("bler"),
            raw_data=json.dumps(results),
        )
        db.add(result)
        db.commit()
        db.refresh(result)

        await manager.broadcast({
            "type": "measurement_result",
            "data": {
                "id": result.id,
                "timestamp": result.timestamp.isoformat(),
                "setting_name": setting.name,
                "rat": setting.rat,
                **results,
            },
        })

        return {"status": "success", "result_id": result.id, "data": results}

    except MT8821CError as e:
        result = MeasurementResult(
            setting_id=setting.id,
            measurement_type=setting.rat,
            status="failed",
            raw_data=json.dumps({"error": str(e)}),
        )
        db.add(result)
        db.commit()

        await manager.broadcast({"type": "measurement_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# WebSocket エンドポイント
# ------------------------------------------------------------------
@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # クライアントからのメッセージ待機（切断検出用）
    except WebSocketDisconnect:
        manager.disconnect(ws)
