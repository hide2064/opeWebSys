"""
計測器制御 API のテスト (/api/instrument, /ws)
MT8821C TCP 接続はモックで代替する
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from instrument.mt8821c import MT8821CError


BASE_SETTING = {
    "name": "計測テスト設定",
    "rat": "LTE",
    "duplex_mode": "FDD",
    "frequency": 2100.0,
    "bandwidth": 10.0,
    "power_level": -20.0,
    "expected_power": -10.0,
    "meas_count": 1,
}

MEASURE_RESULT = {
    "tx_power": -25.30,
    "evm": 1.23,
    "frequency_error": 150.0,
    "bler": 0.0001,
}


def _create_setting(client):
    return client.post("/api/settings/", json=BASE_SETTING).json()


# ---------------------------------------------------------------------------
# GET /api/instrument/status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_disconnected_by_default(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = False
            mock_inst.host = "192.168.1.100"
            mock_inst.port = 5025
            resp = client.get("/api/instrument/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["host"] == "192.168.1.100"
        assert data["port"] == 5025

    def test_connected_status(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            mock_inst.host = "192.168.1.100"
            mock_inst.port = 5025
            resp = client.get("/api/instrument/status")
        assert resp.json()["connected"] is True


# ---------------------------------------------------------------------------
# POST /api/instrument/connect
# ---------------------------------------------------------------------------

class TestConnect:
    def test_connect_success(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.identify.return_value = "ANRITSU,MT8821C,0,1.00"
            resp = client.post("/api/instrument/connect", json={"host": "192.168.1.100"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert "ANRITSU" in data["identity"]

    def test_connect_updates_host(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.identify.return_value = "IDN"
            client.post("/api/instrument/connect", json={"host": "10.0.0.50"})
            assert mock_inst.host == "10.0.0.50"

    def test_connect_failure_returns_503(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.connect.side_effect = MT8821CError("接続失敗")
            resp = client.post("/api/instrument/connect", json={"host": "192.168.1.100"})
        assert resp.status_code == 503

    def test_connect_without_body(self, client):
        """body なしでも動作する"""
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.identify.return_value = "IDN"
            resp = client.post("/api/instrument/connect")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/instrument/disconnect
# ---------------------------------------------------------------------------

class TestDisconnect:
    def test_disconnect_success(self, client):
        resp = client.post("/api/instrument/disconnect")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disconnected"

    def test_disconnect_calls_instrument(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            client.post("/api/instrument/disconnect")
            mock_inst.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/instrument/measure
# ---------------------------------------------------------------------------

class TestMeasure:
    def test_not_connected_returns_503(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = False
            s = _create_setting(client)
            resp = client.post("/api/instrument/measure", json={"setting_id": s["id"]})
        assert resp.status_code == 503

    def test_setting_not_found_returns_404(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            resp = client.post("/api/instrument/measure", json={"setting_id": 9999})
        assert resp.status_code == 404

    def test_measure_success(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            mock_inst.apply_setting.return_value = None
            mock_inst.measure.return_value = MEASURE_RESULT

            s = _create_setting(client)
            resp = client.post("/api/instrument/measure", json={"setting_id": s["id"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["tx_power"] == pytest.approx(-25.30)
        assert data["data"]["evm"] == pytest.approx(1.23)
        assert data["data"]["frequency_error"] == pytest.approx(150.0)
        assert data["data"]["bler"] == pytest.approx(0.0001)
        assert "result_id" in data

    def test_measure_saves_result_to_db(self, client, db):
        """測定成功時に DB に結果が保存される"""
        from db.models import MeasurementResult
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            mock_inst.apply_setting.return_value = None
            mock_inst.measure.return_value = MEASURE_RESULT

            s = _create_setting(client)
            resp = client.post("/api/instrument/measure", json={"setting_id": s["id"]})

        result_id = resp.json()["result_id"]
        db.expire_all()
        saved = db.query(MeasurementResult).filter_by(id=result_id).first()
        assert saved is not None
        assert saved.status == "success"
        assert saved.tx_power == pytest.approx(-25.30)

    def test_measure_instrument_error_returns_500(self, client):
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            mock_inst.apply_setting.side_effect = MT8821CError("SCPI エラー")

            s = _create_setting(client)
            resp = client.post("/api/instrument/measure", json={"setting_id": s["id"]})

        assert resp.status_code == 500

    def test_measure_error_saved_to_db(self, client, db):
        """測定失敗時も DB に failed レコードが保存される"""
        from db.models import MeasurementResult
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            mock_inst.apply_setting.side_effect = MT8821CError("通信エラー")

            s = _create_setting(client)
            client.post("/api/instrument/measure", json={"setting_id": s["id"]})

        db.expire_all()
        results = db.query(MeasurementResult).filter_by(setting_id=s["id"]).all()
        assert len(results) == 1
        assert results[0].status == "failed"

    def test_apply_setting_called_with_correct_params(self, client):
        """DB から読み込んだ設定パラメータが apply_setting に渡される"""
        with patch("api.instrument.instrument") as mock_inst:
            mock_inst.is_connected = True
            mock_inst.apply_setting.return_value = None
            mock_inst.measure.return_value = MEASURE_RESULT

            s = _create_setting(client)
            client.post("/api/instrument/measure", json={"setting_id": s["id"]})

            mock_inst.apply_setting.assert_called_once_with(
                2100.0,    # frequency
                10.0,      # bandwidth
                -20.0,     # power_level
                "FDD",     # duplex_mode
                -10.0,     # expected_power
                None,      # channel_number
                1,         # meas_count
            )


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
