"""
設定 CRUD API のテスト (/api/settings)
"""
import pytest

# ---------------------------------------------------------------------------
# テストデータ
# ---------------------------------------------------------------------------

BASE_SETTING = {
    "name": "LTE Band1 テスト",
    "rat": "LTE",
    "duplex_mode": "FDD",
    "frequency": 2100.0,
    "bandwidth": 10.0,
    "channel_number": 300,
    "power_level": -20.0,
    "expected_power": -10.0,
    "meas_count": 3,
}


def _create(client, overrides=None):
    body = {**BASE_SETTING, **(overrides or {})}
    return client.post("/api/settings/", json=body)


# ---------------------------------------------------------------------------
# POST /api/settings/
# ---------------------------------------------------------------------------

class TestCreateSetting:
    def test_success_returns_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201

    def test_response_contains_all_fields(self, client):
        data = _create(client).json()
        assert data["name"] == "LTE Band1 テスト"
        assert data["rat"] == "LTE"
        assert data["duplex_mode"] == "FDD"
        assert data["frequency"] == 2100.0
        assert data["bandwidth"] == 10.0
        assert data["channel_number"] == 300
        assert data["power_level"] == -20.0
        assert data["expected_power"] == -10.0
        assert data["meas_count"] == 3
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_channel_number_optional(self, client):
        resp = _create(client, {"channel_number": None})
        assert resp.status_code == 201
        assert resp.json()["channel_number"] is None

    def test_missing_frequency_returns_422(self, client):
        body = {k: v for k, v in BASE_SETTING.items() if k != "frequency"}
        resp = client.post("/api/settings/", json=body)
        assert resp.status_code == 422

    def test_missing_name_returns_422(self, client):
        body = {k: v for k, v in BASE_SETTING.items() if k != "name"}
        resp = client.post("/api/settings/", json=body)
        assert resp.status_code == 422

    def test_defaults_applied(self, client):
        """必須項目のみで作成した場合デフォルト値が入る"""
        resp = client.post("/api/settings/", json={"name": "最小設定", "frequency": 900.0})
        assert resp.status_code == 201
        data = resp.json()
        assert data["rat"] == "LTE"
        assert data["duplex_mode"] == "FDD"
        assert data["bandwidth"] == 10.0
        assert data["power_level"] == -20.0
        assert data["expected_power"] == -10.0
        assert data["meas_count"] == 1


# ---------------------------------------------------------------------------
# GET /api/settings/
# ---------------------------------------------------------------------------

class TestListSettings:
    def test_empty_list(self, client):
        resp = client.get("/api/settings/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_created(self, client):
        _create(client, {"name": "設定A"})
        _create(client, {"name": "設定B"})
        data = client.get("/api/settings/").json()
        assert len(data) == 2

    def test_ordered_by_updated_at_desc(self, client):
        _create(client, {"name": "古い設定"})
        _create(client, {"name": "新しい設定"})
        data = client.get("/api/settings/").json()
        # 新しい順に返ってくる
        assert data[0]["name"] == "新しい設定"


# ---------------------------------------------------------------------------
# GET /api/settings/{id}
# ---------------------------------------------------------------------------

class TestGetSetting:
    def test_success(self, client):
        created = _create(client).json()
        resp = client.get(f"/api/settings/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_not_found_returns_404(self, client):
        resp = client.get("/api/settings/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/settings/{id}
# ---------------------------------------------------------------------------

class TestUpdateSetting:
    def test_update_success(self, client):
        created = _create(client).json()
        body = {**BASE_SETTING, "name": "更新後", "frequency": 1800.0, "meas_count": 5}
        resp = client.put(f"/api/settings/{created['id']}", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新後"
        assert data["frequency"] == 1800.0
        assert data["meas_count"] == 5

    def test_update_not_found_returns_404(self, client):
        resp = client.put("/api/settings/9999", json=BASE_SETTING)
        assert resp.status_code == 404

    def test_update_all_parameters(self, client):
        created = _create(client).json()
        updated = {
            "name": "5G NR テスト",
            "rat": "NR5G",
            "duplex_mode": "TDD",
            "frequency": 3700.0,
            "bandwidth": 100.0,
            "channel_number": 630000,
            "power_level": -15.0,
            "expected_power": -5.0,
            "meas_count": 10,
        }
        resp = client.put(f"/api/settings/{created['id']}", json=updated)
        assert resp.status_code == 200
        data = resp.json()
        for key, val in updated.items():
            assert data[key] == val


# ---------------------------------------------------------------------------
# DELETE /api/settings/{id}
# ---------------------------------------------------------------------------

class TestDeleteSetting:
    def test_delete_success_returns_204(self, client):
        created = _create(client).json()
        resp = client.delete(f"/api/settings/{created['id']}")
        assert resp.status_code == 204

    def test_deleted_setting_is_gone(self, client):
        created = _create(client).json()
        client.delete(f"/api/settings/{created['id']}")
        assert client.get(f"/api/settings/{created['id']}").status_code == 404

    def test_delete_not_found_returns_404(self, client):
        resp = client.delete("/api/settings/9999")
        assert resp.status_code == 404

    def test_delete_removes_from_list(self, client):
        _create(client, {"name": "削除対象"})
        keep = _create(client, {"name": "残す設定"}).json()
        delete_id = [s for s in client.get("/api/settings/").json()
                     if s["name"] == "削除対象"][0]["id"]
        client.delete(f"/api/settings/{delete_id}")
        remaining = client.get("/api/settings/").json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == keep["id"]
