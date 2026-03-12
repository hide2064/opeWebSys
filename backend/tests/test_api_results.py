"""
測定結果 API のテスト (/api/results)
"""
import json
import pytest
from db.models import MeasurementResult, Setting


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

BASE_SETTING = {
    "name": "テスト設定",
    "rat": "LTE",
    "duplex_mode": "FDD",
    "frequency": 2100.0,
    "bandwidth": 10.0,
    "power_level": -20.0,
    "expected_power": -10.0,
    "meas_count": 1,
}


def _create_setting(client):
    return client.post("/api/settings/", json=BASE_SETTING).json()


def _seed_result(db, setting_id: int, status: str = "success", **kwargs) -> MeasurementResult:
    """DB に直接テスト用結果レコードを挿入する"""
    defaults = dict(
        tx_power=-25.30, evm=1.23, frequency_error=150.0, bler=0.0001,
        measurement_type="LTE",
        raw_data=json.dumps({"tx_power": -25.30}),
    )
    defaults.update(kwargs)
    result = MeasurementResult(
        setting_id=setting_id,
        status=status,
        **defaults,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


# ---------------------------------------------------------------------------
# GET /api/results/
# ---------------------------------------------------------------------------

class TestListResults:
    def test_empty_list(self, client):
        resp = client.get("/api/results/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_seeded_results(self, client, db):
        s = _create_setting(client)
        _seed_result(db, s["id"])
        _seed_result(db, s["id"])
        data = client.get("/api/results/").json()
        assert len(data) == 2

    def test_limit_parameter(self, client, db):
        s = _create_setting(client)
        for _ in range(5):
            _seed_result(db, s["id"])
        data = client.get("/api/results/?limit=3").json()
        assert len(data) == 3

    def test_filter_by_setting_id(self, client, db):
        s1 = _create_setting(client)
        s2 = client.post("/api/settings/", json={**BASE_SETTING, "name": "設定2"}).json()
        _seed_result(db, s1["id"])
        _seed_result(db, s1["id"])
        _seed_result(db, s2["id"])

        data = client.get(f"/api/results/?setting_id={s1['id']}").json()
        assert len(data) == 2
        assert all(r["setting_id"] == s1["id"] for r in data)

    def test_response_fields(self, client, db):
        s = _create_setting(client)
        _seed_result(db, s["id"])
        r = client.get("/api/results/").json()[0]
        assert "id" in r
        assert "setting_id" in r
        assert "measurement_type" in r
        assert "timestamp" in r
        assert "status" in r
        assert "tx_power" in r
        assert "evm" in r
        assert "frequency_error" in r
        assert "bler" in r

    def test_ordered_by_timestamp_desc(self, client, db):
        s = _create_setting(client)
        r1 = _seed_result(db, s["id"], tx_power=-25.0)
        r2 = _seed_result(db, s["id"], tx_power=-26.0)
        data = client.get("/api/results/").json()
        # 新しい順: r2 が先
        assert data[0]["id"] == r2.id

    def test_failed_result_included(self, client, db):
        s = _create_setting(client)
        _seed_result(db, s["id"], status="failed", tx_power=None, evm=None,
                     frequency_error=None, bler=None)
        data = client.get("/api/results/").json()
        assert len(data) == 1
        assert data[0]["status"] == "failed"
        assert data[0]["tx_power"] is None


# ---------------------------------------------------------------------------
# GET /api/results/{id}
# ---------------------------------------------------------------------------

class TestGetResult:
    def test_success(self, client, db):
        s = _create_setting(client)
        r = _seed_result(db, s["id"])
        resp = client.get(f"/api/results/{r.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == r.id
        assert data["tx_power"] == pytest.approx(-25.30)
        assert data["evm"] == pytest.approx(1.23)

    def test_not_found_returns_404(self, client):
        resp = client.get("/api/results/9999")
        assert resp.status_code == 404
