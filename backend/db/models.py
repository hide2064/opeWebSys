from datetime import datetime
from sqlalchemy import Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rat: Mapped[str] = mapped_column(String(20), nullable=False, default="LTE")       # LTE / WCDMA / GSM / NR5G
    duplex_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="FDD")  # FDD / TDD
    frequency: Mapped[float] = mapped_column(Float, nullable=False)                   # MHz (DL中心周波数)
    bandwidth: Mapped[float] = mapped_column(Float, nullable=False)                   # MHz
    channel_number: Mapped[int | None] = mapped_column(Integer, nullable=True)        # EARFCN / UARFCN / ARFCN
    power_level: Mapped[float] = mapped_column(Float, nullable=False, default=-20.0)  # 参照レベル (dBm)
    expected_power: Mapped[float] = mapped_column(Float, nullable=False, default=-10.0)  # 期待UE送信電力 (dBm)
    meas_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)       # 測定回数
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    results: Mapped[list["MeasurementResult"]] = relationship("MeasurementResult", back_populates="setting")


class MeasurementResult(Base):
    __tablename__ = "measurement_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    setting_id: Mapped[int] = mapped_column(Integer, ForeignKey("settings.id"), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success / failed
    tx_power: Mapped[float | None] = mapped_column(Float, nullable=True)          # dBm
    evm: Mapped[float | None] = mapped_column(Float, nullable=True)               # %
    frequency_error: Mapped[float | None] = mapped_column(Float, nullable=True)  # Hz
    bler: Mapped[float | None] = mapped_column(Float, nullable=True)             # %
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)            # JSON

    setting: Mapped["Setting"] = relationship("Setting", back_populates="results")
