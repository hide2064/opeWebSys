from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import create_tables
from api.instrument import router as instrument_router, ws_router
from api.settings import router as settings_router
from api.results import router as results_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="MT8821C Web Control System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(instrument_router, prefix="/api/instrument", tags=["instrument"])
app.include_router(ws_router, tags=["websocket"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(results_router, prefix="/api/results", tags=["results"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
