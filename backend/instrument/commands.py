# MT8821C SCPI コマンド定義
# 参考: Anritsu MT8821C Remote Control Manual

class CMD:
    # --- システム ---
    IDENTIFY    = "*IDN?"
    RESET       = "*RST"
    CLEAR       = "*CLS"
    ERROR       = "SYST:ERR?"
    OPC_QUERY   = "*OPC?"

    # --- 周波数設定 ---
    FREQ_CENTER       = "FREQ:CENT {freq}MHZ"
    FREQ_CENTER_QUERY = "FREQ:CENT?"

    # --- 帯域幅設定 ---
    BAND_WIDTH        = "BAND:RES {bw}MHZ"
    BAND_WIDTH_QUERY  = "BAND:RES?"

    # --- 電力レベル設定 ---
    LEVEL_REF         = "DISP:WIND:TRAC:Y:RLEV {level}DBM"
    LEVEL_REF_QUERY   = "DISP:WIND:TRAC:Y:RLEV?"

    # --- 測定トリガ ---
    MEAS_INIT         = "INIT:IMM"
    MEAS_ABORT        = "ABOR"

    # --- LTE 測定結果取得 ---
    LTE_TX_POWER      = "FETC:LTE:UL:POW?"
    LTE_EVM           = "FETC:LTE:EVM?"
    LTE_FREQ_ERROR    = "FETC:LTE:FERR?"
    LTE_BLER          = "FETC:LTE:BLER?"
    LTE_RSSI          = "FETC:LTE:RSSI?"

    # --- W-CDMA 測定結果取得 ---
    WCDMA_TX_POWER    = "FETC:WCDM:POW?"
    WCDMA_EVM         = "FETC:WCDM:EVM?"
    WCDMA_FREQ_ERROR  = "FETC:WCDM:FERR?"

    # --- GSM 測定結果取得 ---
    GSM_TX_POWER      = "FETC:GSM:POW?"
    GSM_FREQ_ERROR    = "FETC:GSM:FERR?"
    GSM_BER           = "FETC:GSM:BER?"

    # --- 5G NR 測定結果取得 ---
    NR5G_TX_POWER     = "FETC:NR5G:UL:POW?"
    NR5G_EVM          = "FETC:NR5G:EVM?"
    NR5G_FREQ_ERROR   = "FETC:NR5G:FERR?"
    NR5G_BLER         = "FETC:NR5G:BLER?"


# SCPI 無効値 (IEEE 488.2 Not-a-Number)
SCPI_NAN = 9.91e+37
