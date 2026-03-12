"""
MT8821C クラスのユニットテスト
TCP ソケットはすべてモックで代替する
"""
import pytest
from unittest.mock import MagicMock, patch, call

from instrument.mt8821c import MT8821C, MT8821CError
from instrument.commands import SCPI_NAN


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def make_inst() -> MT8821C:
    return MT8821C(host="192.168.1.100", port=5025, timeout=5.0)


def connected_inst(mock_sock) -> MT8821C:
    """ソケット接続済みの MT8821C インスタンスを返す"""
    inst = make_inst()
    inst._socket = mock_sock
    return inst


# ---------------------------------------------------------------------------
# 接続管理
# ---------------------------------------------------------------------------

class TestConnect:
    def test_connect_success(self):
        inst = make_inst()
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_cls.return_value = mock_sock

            inst.connect()

            mock_sock.connect.assert_called_once_with(("192.168.1.100", 5025))
            assert inst.is_connected

    def test_connect_failure_raises_mt8821c_error(self):
        inst = make_inst()
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")
            mock_cls.return_value = mock_sock

            with pytest.raises(MT8821CError, match="接続失敗"):
                inst.connect()
        assert not inst.is_connected

    def test_connect_idempotent(self):
        """既接続の場合は再接続しない"""
        inst = make_inst()
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_cls.return_value = mock_sock

            inst.connect()
            inst.connect()  # 2回目

            mock_sock.connect.assert_called_once()


class TestDisconnect:
    def test_disconnect_closes_socket(self):
        inst = make_inst()
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_cls.return_value = mock_sock

            inst.connect()
            inst.disconnect()

            mock_sock.close.assert_called_once()
            assert not inst.is_connected

    def test_disconnect_when_not_connected_is_safe(self):
        inst = make_inst()
        inst.disconnect()  # エラーにならない


# ---------------------------------------------------------------------------
# 低レベル通信
# ---------------------------------------------------------------------------

class TestWrite:
    def test_write_appends_newline(self):
        mock_sock = MagicMock()
        inst = connected_inst(mock_sock)

        inst.write("*RST")

        mock_sock.sendall.assert_called_once_with(b"*RST\n")

    def test_write_strips_extra_whitespace(self):
        mock_sock = MagicMock()
        inst = connected_inst(mock_sock)

        inst.write("  *CLS  ")

        mock_sock.sendall.assert_called_once_with(b"*CLS\n")

    def test_write_not_connected_raises(self):
        inst = make_inst()
        with pytest.raises(MT8821CError):
            inst.write("*RST")


class TestQuery:
    def test_query_returns_stripped_response(self):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"ANRITSU,MT8821C,0,1.00\n"]
        inst = connected_inst(mock_sock)

        result = inst.query("*IDN?")

        assert result == "ANRITSU,MT8821C,0,1.00"

    def test_query_multi_chunk(self):
        """複数チャンクで受信しても正しく結合される"""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"-25", b".30\n"]
        inst = connected_inst(mock_sock)

        result = inst.query("FETC:LTE:UL:POW?")

        assert result == "-25.30"


class TestQueryFloat:
    def test_valid_float(self):
        inst = make_inst()
        with patch.object(inst, "query", return_value="-25.30"):
            assert inst.query_float("CMD?") == pytest.approx(-25.30)

    def test_scpi_nan_returns_none(self):
        inst = make_inst()
        with patch.object(inst, "query", return_value=str(SCPI_NAN)):
            assert inst.query_float("CMD?") is None

    def test_non_numeric_returns_none(self):
        inst = make_inst()
        with patch.object(inst, "query", return_value="ERROR"):
            assert inst.query_float("CMD?") is None

    def test_positive_float(self):
        inst = make_inst()
        with patch.object(inst, "query", return_value="1.234567"):
            assert inst.query_float("CMD?") == pytest.approx(1.234567, rel=1e-5)


# ---------------------------------------------------------------------------
# 設定適用
# ---------------------------------------------------------------------------

class TestApplySetting:
    def _collect_writes(self, inst, **kwargs) -> list:
        sent = []
        with patch.object(inst, "write", side_effect=lambda cmd: sent.append(cmd)):
            inst.apply_setting(**kwargs)
        return sent

    def test_all_commands_sent(self):
        inst = make_inst()
        sent = self._collect_writes(
            inst,
            frequency=2100.0, bandwidth=10.0, power_level=-20.0,
            duplex_mode="FDD", expected_power=-10.0,
            channel_number=300, meas_count=3,
        )
        assert "CALL:DUPLEX FDD" in sent
        assert "FREQ:CENT 2100.0MHZ" in sent
        assert "BAND:RES 10.0MHZ" in sent
        assert "DISP:WIND:TRAC:Y:RLEV -20.0DBM" in sent
        assert "POW:EXP -10.0DBM" in sent
        assert "SENS:AVER:COUN 3" in sent
        assert "FREQ:CHAN:DL 300" in sent

    def test_channel_number_none_not_sent(self):
        inst = make_inst()
        sent = self._collect_writes(
            inst,
            frequency=2100.0, bandwidth=10.0, power_level=-20.0,
        )
        assert not any("FREQ:CHAN:DL" in s for s in sent)

    def test_duplex_mode_uppercased(self):
        inst = make_inst()
        sent = self._collect_writes(
            inst,
            frequency=2100.0, bandwidth=10.0, power_level=-20.0,
            duplex_mode="tdd",
        )
        assert "CALL:DUPLEX TDD" in sent

    def test_meas_count_minimum_1(self):
        """meas_count=0 でも SENS:AVER:COUN 1 が送信される"""
        inst = make_inst()
        sent = self._collect_writes(
            inst,
            frequency=2100.0, bandwidth=10.0, power_level=-20.0,
            meas_count=0,
        )
        assert "SENS:AVER:COUN 1" in sent


# ---------------------------------------------------------------------------
# 測定実行
# ---------------------------------------------------------------------------

class TestMeasure:
    """各 RAT の測定結果キーを確認する"""

    def _measure(self, rat: str, return_val=None):
        inst = make_inst()
        inst._socket = MagicMock()
        with patch.object(inst, "write"), \
             patch.object(inst, "wait_opc"), \
             patch.object(inst, "query_float", return_value=return_val):
            return inst.measure(rat)

    def _measure_with_mapping(self, rat: str, mapping: dict):
        """コマンド内の部分文字列で戻り値を切り替えるヘルパー"""
        inst = make_inst()
        inst._socket = MagicMock()

        def side_effect(cmd: str):
            for key, val in mapping.items():
                if key in cmd:
                    return val
            return None

        with patch.object(inst, "write"), \
             patch.object(inst, "wait_opc"), \
             patch.object(inst, "query_float", side_effect=side_effect):
            return inst.measure(rat)

    def test_measure_lte_keys(self):
        result = self._measure_with_mapping("LTE", {
            "UL:POW": -25.30, "EVM": 1.23, "FERR": 150.0, "BLER": 0.0001,
        })
        assert result["tx_power"] == -25.30
        assert result["evm"] == 1.23
        assert result["frequency_error"] == 150.0
        assert result["bler"] == 0.0001

    def test_measure_wcdma_bler_is_none(self):
        result = self._measure("WCDMA", return_val=-30.0)
        assert result["tx_power"] == -30.0
        assert result["bler"] is None

    def test_measure_gsm_evm_is_none(self):
        result = self._measure("GSM", return_val=-28.0)
        assert result["tx_power"] == -28.0
        assert result["evm"] is None
        assert "bler" in result   # BER として存在

    def test_measure_nr5g_keys(self):
        result = self._measure("NR5G", return_val=-20.0)
        assert result["tx_power"] == -20.0
        assert result["evm"] == -20.0
        assert result["frequency_error"] == -20.0
        assert result["bler"] == -20.0

    def test_measure_rat_case_insensitive(self):
        """RAT は大文字小文字を問わない"""
        result = self._measure("lte", return_val=-25.0)
        assert "tx_power" in result

    def test_measure_unknown_rat_raises(self):
        inst = make_inst()
        inst._socket = MagicMock()
        with patch.object(inst, "write"), patch.object(inst, "wait_opc"):
            with pytest.raises(MT8821CError, match="未対応の RAT"):
                inst.measure("UNKNOWN")
