import socket
import threading
import time
from typing import Optional
from instrument.commands import CMD, SCPI_NAN


class MT8821CError(Exception):
    pass


class MT8821C:
    """Anritsu MT8821C SCPI over TCP/IP 制御クラス (Port 5025)"""

    def __init__(self, host: str, port: int = 5025, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 接続管理
    # ------------------------------------------------------------------

    def connect(self) -> None:
        with self._lock:
            if self._socket:
                return
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                self._socket = sock
            except Exception as e:
                raise MT8821CError(f"接続失敗 ({self.host}:{self.port}): {e}")

    def disconnect(self) -> None:
        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    # ------------------------------------------------------------------
    # 低レベル通信
    # ------------------------------------------------------------------

    def _send(self, command: str) -> None:
        if not self._socket:
            raise MT8821CError("MT8821C に接続されていません")
        self._socket.sendall((command.strip() + "\n").encode("ascii"))

    def _recv(self) -> str:
        if not self._socket:
            raise MT8821CError("MT8821C に接続されていません")
        data = b""
        while True:
            try:
                chunk = self._socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            except socket.timeout:
                break
        return data.decode("ascii", errors="replace").strip()

    def write(self, command: str) -> None:
        with self._lock:
            self._send(command)

    def query(self, command: str) -> str:
        with self._lock:
            self._send(command)
            return self._recv()

    def query_float(self, command: str) -> Optional[float]:
        """クエリ結果を float に変換。SCPI NaN/エラー値は None を返す。"""
        try:
            val = float(self.query(command))
            if abs(val) >= SCPI_NAN * 0.9:
                return None
            return round(val, 6)
        except (ValueError, MT8821CError):
            return None

    # ------------------------------------------------------------------
    # 汎用コマンド
    # ------------------------------------------------------------------

    def identify(self) -> str:
        return self.query(CMD.IDENTIFY)

    def reset(self) -> None:
        self.write(CMD.RESET)
        time.sleep(2)

    def get_error(self) -> str:
        return self.query(CMD.ERROR)

    def wait_opc(self) -> None:
        self.query(CMD.OPC_QUERY)

    # ------------------------------------------------------------------
    # 設定適用
    # ------------------------------------------------------------------

    def apply_setting(
        self,
        frequency: float,
        bandwidth: float,
        power_level: float,
        duplex_mode: str = "FDD",
        expected_power: float = -10.0,
        channel_number: int | None = None,
        meas_count: int = 1,
    ) -> None:
        """MT8821C へ全設定パラメータを送信する"""
        self.write(CMD.DUPLEX_MODE.format(mode=duplex_mode.upper()))
        self.write(CMD.FREQ_CENTER.format(freq=frequency))
        self.write(CMD.BAND_WIDTH.format(bw=bandwidth))
        self.write(CMD.LEVEL_REF.format(level=power_level))
        self.write(CMD.EXP_POWER.format(power=expected_power))
        self.write(CMD.MEAS_COUNT.format(count=max(1, meas_count)))
        if channel_number is not None:
            self.write(CMD.CHAN_DL.format(ch=channel_number))

    # ------------------------------------------------------------------
    # 測定実行
    # ------------------------------------------------------------------

    def measure(self, rat: str) -> dict:
        """
        指定 RAT の測定を実行して結果を返す。
        rat: 'LTE' | 'WCDMA' | 'GSM' | 'NR5G'
        """
        self.write(CMD.MEAS_INIT)
        self.wait_opc()

        rat = rat.upper()
        if rat == "LTE":
            return {
                "tx_power":       self.query_float(CMD.LTE_TX_POWER),
                "evm":            self.query_float(CMD.LTE_EVM),
                "frequency_error": self.query_float(CMD.LTE_FREQ_ERROR),
                "bler":           self.query_float(CMD.LTE_BLER),
            }
        elif rat == "WCDMA":
            return {
                "tx_power":       self.query_float(CMD.WCDMA_TX_POWER),
                "evm":            self.query_float(CMD.WCDMA_EVM),
                "frequency_error": self.query_float(CMD.WCDMA_FREQ_ERROR),
                "bler":           None,
            }
        elif rat == "GSM":
            return {
                "tx_power":       self.query_float(CMD.GSM_TX_POWER),
                "evm":            None,
                "frequency_error": self.query_float(CMD.GSM_FREQ_ERROR),
                "bler":           self.query_float(CMD.GSM_BER),
            }
        elif rat == "NR5G":
            return {
                "tx_power":       self.query_float(CMD.NR5G_TX_POWER),
                "evm":            self.query_float(CMD.NR5G_EVM),
                "frequency_error": self.query_float(CMD.NR5G_FREQ_ERROR),
                "bler":           self.query_float(CMD.NR5G_BLER),
            }
        else:
            raise MT8821CError(f"未対応の RAT: {rat}")
