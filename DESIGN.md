# MT8821C Web Control System 設計書

**バージョン**: 1.0.0
**作成日**: 2026-03-12

---

## 1. システム概要

Anritsu MT8821C（無線通信アナライザ）をブラウザから LAN 経由でリモート制御し、測定結果をリアルタイムで Web 画面に表示するシステム。測定設定値および測定結果は MySQL データベースに永続化する。

---

## 2. システム構成図

```
┌──────────────────────────────────────────────────────────────┐
│  クライアント (ブラウザ)                                       │
│  Vue.js 3 + Bootstrap 5 + Chart.js                          │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP / WebSocket (Port 80)
┌────────────────────────▼─────────────────────────────────────┐
│  nginx (Docker)  ※リバースプロキシ                            │
│  - /api  → backend:8000 (REST API)                          │
│  - /ws   → backend:8000 (WebSocket)                         │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP / WebSocket (Port 8000)
┌────────────────────────▼─────────────────────────────────────┐
│  Backend: FastAPI + Python 3.12 (Docker)                    │
│  - REST API (instrument / settings / results)               │
│  - WebSocket サーバ (測定結果リアルタイム配信)                  │
│  - MT8821C SCPI 制御 (TCP Socket)                            │
│  - SQLAlchemy ORM                                           │
└──────────┬──────────────────────────┬────────────────────────┘
           │ TCP Port 5025 (SCPI)     │ TCP Port 3306
┌──────────▼──────────┐   ┌───────────▼────────────────────────┐
│  Anritsu MT8821C    │   │  MySQL 8.0 (Docker)                │
│  192.168.1.100      │   │  DB: mt8821c_db                    │
└─────────────────────┘   └────────────────────────────────────┘
```

---

## 3. 技術スタック

| 層 | 技術 | バージョン |
|---|---|---|
| フロントエンド | Vue.js | 3.4 |
| フロントエンド | Bootstrap | 5.3 |
| フロントエンド | Chart.js | 4.4 |
| Web サーバ | nginx | alpine |
| バックエンド | Python | 3.12 |
| バックエンド | FastAPI | 0.115 |
| バックエンド | uvicorn | 0.30 |
| ORM | SQLAlchemy | 2.0 |
| DB ドライバ | PyMySQL | 1.1 |
| データベース | MySQL | 8.0 |
| コンテナ | Docker / Docker Compose | - |
| 計測器通信 | SCPI over TCP (raw socket) | Port 5025 |

---

## 4. ディレクトリ構成

```
opeWebSys/
├── docker-compose.yml          # サービス定義 (mysql / backend / frontend)
├── DESIGN.md                   # 本設計書
├── backend/
│   ├── Dockerfile              # Python 3.12-slim ベース
│   ├── requirements.txt        # Python 依存パッケージ
│   ├── .env                    # 環境変数 (DB URL / MT8821C IP 等)
│   ├── main.py                 # FastAPI アプリ起動・ルーター登録
│   ├── db/
│   │   ├── database.py         # SQLAlchemy エンジン・セッション・テーブル作成
│   │   └── models.py           # ORM モデル定義
│   ├── instrument/
│   │   ├── mt8821c.py          # MT8821C SCPI 制御クラス
│   │   └── commands.py         # SCPI コマンド定数定義
│   └── api/
│       ├── instrument.py       # 計測器制御 API + WebSocket
│       ├── settings.py         # 測定設定 CRUD API
│       └── results.py          # 測定結果取得 API
└── frontend/
    ├── index.html              # シングルページアプリ (SPA)
    └── nginx.conf              # nginx リバースプロキシ設定
```

---

## 5. データベース設計

### 5.1 settings テーブル（測定設定）

| カラム名 | 型 | 説明 |
|---|---|---|
| id | INT PK AUTO_INCREMENT | 設定ID |
| name | VARCHAR(100) NOT NULL | 設定名 |
| rat | VARCHAR(20) NOT NULL | 無線方式 (LTE / WCDMA / GSM / NR5G) |
| frequency | FLOAT NOT NULL | 中心周波数 (MHz) |
| bandwidth | FLOAT NOT NULL | 帯域幅 (MHz) |
| power_level | FLOAT NOT NULL | 電力レベル (dBm) |
| channel_number | INT NULL | チャネル番号 |
| created_at | DATETIME | 作成日時 |
| updated_at | DATETIME | 更新日時 |

### 5.2 measurement_results テーブル（測定結果）

| カラム名 | 型 | 説明 |
|---|---|---|
| id | INT PK AUTO_INCREMENT | 結果ID |
| setting_id | INT FK(settings.id) | 使用した設定ID |
| measurement_type | VARCHAR(20) NOT NULL | 測定種別 (LTE / WCDMA / GSM / NR5G) |
| timestamp | DATETIME | 測定日時 |
| status | VARCHAR(20) NOT NULL | 成否 (success / failed) |
| tx_power | FLOAT NULL | 送信電力 (dBm) |
| evm | FLOAT NULL | EVM (%) |
| frequency_error | FLOAT NULL | 周波数誤差 (Hz) |
| bler | FLOAT NULL | BLER / BER (%) |
| raw_data | TEXT NULL | 生データ (JSON) |

---

## 6. API 仕様

### 6.1 計測器制御 API (`/api/instrument`)

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/instrument/status` | 接続状態取得 |
| POST | `/api/instrument/connect` | MT8821C へ接続 |
| POST | `/api/instrument/disconnect` | MT8821C から切断 |
| POST | `/api/instrument/measure` | 測定実行 |
| WS | `/ws` | WebSocket (測定結果リアルタイム配信) |

#### POST /api/instrument/connect リクエスト
```json
{ "host": "192.168.1.100" }
```

#### POST /api/instrument/measure リクエスト
```json
{ "setting_id": 1 }
```

#### WebSocket メッセージ (測定完了時)
```json
{
  "type": "measurement_result",
  "data": {
    "id": 10,
    "timestamp": "2026-03-12T10:00:00",
    "setting_name": "LTE Band1",
    "rat": "LTE",
    "tx_power": -25.3,
    "evm": 1.23,
    "frequency_error": 150.0,
    "bler": 0.0001
  }
}
```

### 6.2 設定 API (`/api/settings`)

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/settings/` | 設定一覧取得 |
| GET | `/api/settings/{id}` | 設定取得 |
| POST | `/api/settings/` | 設定作成 |
| PUT | `/api/settings/{id}` | 設定更新 |
| DELETE | `/api/settings/{id}` | 設定削除 |

#### POST/PUT リクエスト Body
```json
{
  "name": "LTE Band1 テスト",
  "rat": "LTE",
  "frequency": 2100.0,
  "bandwidth": 10.0,
  "power_level": -30.0,
  "channel_number": 300
}
```

### 6.3 結果 API (`/api/results`)

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/results/?limit=50` | 結果一覧 (最大200件) |
| GET | `/api/results/?setting_id=1` | 設定IDでフィルタ |
| GET | `/api/results/{id}` | 結果取得 |

---

## 7. MT8821C 通信仕様

### 7.1 接続仕様

| 項目 | 値 |
|---|---|
| プロトコル | SCPI over TCP/IP (Raw Socket) |
| IP アドレス | 192.168.1.100 (設定変更可) |
| ポート番号 | 5025 |
| タイムアウト | 10 秒 |
| 文字コード | ASCII |
| コマンド区切り | `\n` (LF) |

### 7.2 使用 SCPI コマンド一覧

| コマンド | 説明 |
|---|---|
| `*IDN?` | 機器識別情報取得 |
| `*RST` | リセット |
| `*CLS` | ステータスクリア |
| `*OPC?` | 操作完了待ち |
| `SYST:ERR?` | エラー取得 |
| `FREQ:CENT {freq}MHZ` | 中心周波数設定 |
| `BAND:RES {bw}MHZ` | 帯域幅設定 |
| `DISP:WIND:TRAC:Y:RLEV {level}DBM` | 基準電力レベル設定 |
| `INIT:IMM` | 測定開始 |
| `ABOR` | 測定中断 |
| `FETC:LTE:UL:POW?` | LTE 送信電力取得 (dBm) |
| `FETC:LTE:EVM?` | LTE EVM 取得 (%) |
| `FETC:LTE:FERR?` | LTE 周波数誤差取得 (Hz) |
| `FETC:LTE:BLER?` | LTE BLER 取得 (%) |
| `FETC:WCDM:POW?` | W-CDMA 送信電力取得 (dBm) |
| `FETC:WCDM:EVM?` | W-CDMA EVM 取得 (%) |
| `FETC:WCDM:FERR?` | W-CDMA 周波数誤差取得 (Hz) |
| `FETC:GSM:POW?` | GSM 送信電力取得 (dBm) |
| `FETC:GSM:FERR?` | GSM 周波数誤差取得 (Hz) |
| `FETC:GSM:BER?` | GSM BER 取得 (%) |
| `FETC:NR5G:UL:POW?` | 5G NR 送信電力取得 (dBm) |
| `FETC:NR5G:EVM?` | 5G NR EVM 取得 (%) |
| `FETC:NR5G:FERR?` | 5G NR 周波数誤差取得 (Hz) |
| `FETC:NR5G:BLER?` | 5G NR BLER 取得 (%) |

---

## 8. 測定フロー

```
ブラウザ                  Backend (FastAPI)          MT8821C
   │                           │                        │
   │ POST /api/instrument/connect                       │
   │ ─────────────────────────►│                        │
   │                           │─ TCP connect ─────────►│
   │                           │◄─ *IDN? response ──────│
   │◄── { status: connected } ─│                        │
   │                           │                        │
   │ POST /api/instrument/measure { setting_id: 1 }     │
   │ ─────────────────────────►│                        │
   │                           │─ FREQ:CENT 2100MHZ ───►│
   │                           │─ BAND:RES 10MHZ ──────►│
   │                           │─ DISP...RLEV -30DBM ──►│
   │                           │─ INIT:IMM ────────────►│
   │                           │─ *OPC? ───────────────►│
   │                           │◄─ 1 ───────────────────│
   │                           │─ FETC:LTE:UL:POW? ────►│
   │                           │◄─ -25.30 ──────────────│
   │                           │  ... (各測定値取得)      │
   │                           │                        │
   │                           │─ DB 保存               │
   │◄── WS: measurement_result ─│                       │
   │◄── { status: success } ───│                        │
```

---

## 9. Docker 構成

### 9.1 サービス一覧

| サービス名 | イメージ | ポート | 役割 |
|---|---|---|---|
| mysql | mysql:8.0 | 3306 | データベース |
| backend | Python 3.12-slim (build) | 8000 | FastAPI アプリ |
| frontend | nginx:alpine | 80 | 静的ファイル配信 + リバースプロキシ |

### 9.2 起動手順

```bash
# 初回起動 (イメージビルド込み)
docker compose up --build

# バックグラウンド起動
docker compose up -d --build

# 停止
docker compose down

# DB データ含め全削除
docker compose down -v
```

### 9.3 環境変数 (`backend/.env`)

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| DATABASE_URL | mysql+pymysql://...@mysql:3306/mt8821c_db | MySQL 接続 URL |
| MT8821C_HOST | 192.168.1.100 | MT8821C IP アドレス |
| MT8821C_PORT | 5025 | MT8821C ポート番号 |
| MT8821C_TIMEOUT | 10 | 通信タイムアウト (秒) |

---

## 10. アクセス先

| 対象 | URL |
|---|---|
| Web UI | http://localhost |
| API ドキュメント (Swagger) | http://localhost:8000/docs |
| API ヘルスチェック | http://localhost/api/health |

---

## 11. 対応 RAT

| RAT | 規格 | 測定項目 |
|---|---|---|
| LTE | 4G LTE FDD/TDD | TX Power / EVM / Freq Error / BLER |
| WCDMA | 3G W-CDMA | TX Power / EVM / Freq Error |
| GSM | 2G GSM/EDGE | TX Power / Freq Error / BER |
| NR5G | 5G NR | TX Power / EVM / Freq Error / BLER |
