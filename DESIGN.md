# MT8821C Web Control System 設計書

**バージョン**: 1.1.0
**作成日**: 2026-03-12
**更新日**: 2026-03-12

---

## 1. システム概要

Anritsu MT8821C（無線通信アナライザ）をブラウザから LAN 経由でリモート制御し、測定結果をリアルタイムで Web 画面に表示するシステム。測定設定値および測定結果は MySQL データベースに永続化する。

### 主な機能
- ブラウザから MT8821C の全制御パラメータを設定・変更
- 設定を名前付きで複数保存・切り替え
- 測定実行と結果のリアルタイム表示（WebSocket）
- 測定履歴の参照

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
| コンテナ | Docker / Docker Compose | v2 |
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
│   │   ├── database.py         # SQLAlchemy エンジン・セッション・テーブル作成 (起動リトライ付き)
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

| カラム名 | 型 | デフォルト | 説明 |
|---|---|---|---|
| id | INT PK AUTO_INCREMENT | - | 設定ID |
| name | VARCHAR(100) NOT NULL | - | 設定名 |
| rat | VARCHAR(20) NOT NULL | LTE | 無線方式 (LTE / WCDMA / GSM / NR5G) |
| duplex_mode | VARCHAR(10) NOT NULL | FDD | 複信方式 (FDD / TDD) |
| frequency | FLOAT NOT NULL | - | DL 中心周波数 (MHz) |
| bandwidth | FLOAT NOT NULL | - | 帯域幅 (MHz) |
| channel_number | INT NULL | NULL | チャネル番号 (EARFCN / UARFCN / ARFCN / NR-ARFCN) |
| power_level | FLOAT NOT NULL | -20.0 | 参照レベル (dBm) |
| expected_power | FLOAT NOT NULL | -10.0 | 期待 UE 送信電力 (dBm) |
| meas_count | INT NOT NULL | 1 | 測定回数（平均化回数） |
| created_at | DATETIME | now() | 作成日時 |
| updated_at | DATETIME | now() | 更新日時 |

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

#### WebSocket メッセージ形式

測定成功時:
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

測定失敗時:
```json
{ "type": "measurement_error", "error": "エラーメッセージ" }
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
  "duplex_mode": "FDD",
  "frequency": 2100.0,
  "bandwidth": 10.0,
  "channel_number": 300,
  "power_level": -20.0,
  "expected_power": -10.0,
  "meas_count": 3
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
| IP アドレス | 192.168.1.100 (Web UI から変更可) |
| ポート番号 | 5025 |
| タイムアウト | 10 秒 |
| 文字コード | ASCII |
| コマンド区切り | `\n` (LF) |

### 7.2 使用 SCPI コマンド一覧

#### システム
| コマンド | 説明 |
|---|---|
| `*IDN?` | 機器識別情報取得 |
| `*RST` | リセット |
| `*CLS` | ステータスクリア |
| `*OPC?` | 操作完了待ち |
| `SYST:ERR?` | エラー取得 |

#### 設定コマンド（apply_setting で送信）
| コマンド | 説明 | 対応パラメータ |
|---|---|---|
| `CALL:DUPLEX {mode}` | 複信方式設定 | duplex_mode (FDD/TDD) |
| `FREQ:CENT {freq}MHZ` | DL 中心周波数設定 | frequency (MHz) |
| `BAND:RES {bw}MHZ` | 帯域幅設定 | bandwidth (MHz) |
| `DISP:WIND:TRAC:Y:RLEV {level}DBM` | 参照レベル設定 | power_level (dBm) |
| `POW:EXP {power}DBM` | 期待 UE 送信電力設定 | expected_power (dBm) |
| `SENS:AVER:COUN {count}` | 測定回数設定 | meas_count |
| `FREQ:CHAN:DL {ch}` | DL チャネル番号設定 | channel_number (省略可) |

#### 測定トリガ
| コマンド | 説明 |
|---|---|
| `INIT:IMM` | 測定開始 |
| `ABOR` | 測定中断 |

#### LTE 測定結果取得
| コマンド | 説明 |
|---|---|
| `FETC:LTE:UL:POW?` | 送信電力 (dBm) |
| `FETC:LTE:EVM?` | EVM (%) |
| `FETC:LTE:FERR?` | 周波数誤差 (Hz) |
| `FETC:LTE:BLER?` | BLER (%) |

#### W-CDMA 測定結果取得
| コマンド | 説明 |
|---|---|
| `FETC:WCDM:POW?` | 送信電力 (dBm) |
| `FETC:WCDM:EVM?` | EVM (%) |
| `FETC:WCDM:FERR?` | 周波数誤差 (Hz) |

#### GSM 測定結果取得
| コマンド | 説明 |
|---|---|
| `FETC:GSM:POW?` | 送信電力 (dBm) |
| `FETC:GSM:FERR?` | 周波数誤差 (Hz) |
| `FETC:GSM:BER?` | BER (%) |

#### 5G NR 測定結果取得
| コマンド | 説明 |
|---|---|
| `FETC:NR5G:UL:POW?` | 送信電力 (dBm) |
| `FETC:NR5G:EVM?` | EVM (%) |
| `FETC:NR5G:FERR?` | 周波数誤差 (Hz) |
| `FETC:NR5G:BLER?` | BLER (%) |

---

## 8. 測定フロー

```
ブラウザ                  Backend (FastAPI)              MT8821C
   │                           │                            │
   │ POST /api/instrument/connect                           │
   │ ─────────────────────────►│                            │
   │                           │─── TCP connect ───────────►│
   │                           │◄── *IDN? response ─────────│
   │◄── { status: connected } ─│                            │
   │                           │                            │
   │ POST /api/instrument/measure { setting_id: 1 }         │
   │ ─────────────────────────►│                            │
   │                           │  DB から設定を読込          │
   │                           │─── CALL:DUPLEX FDD ───────►│
   │                           │─── FREQ:CENT 2100MHZ ─────►│
   │                           │─── BAND:RES 10MHZ ────────►│
   │                           │─── DISP...RLEV -20DBM ────►│
   │                           │─── POW:EXP -10DBM ────────►│
   │                           │─── SENS:AVER:COUN 1 ──────►│
   │                           │─── INIT:IMM ──────────────►│
   │                           │─── *OPC? ─────────────────►│
   │                           │◄── 1 ──────────────────────│
   │                           │─── FETC:LTE:UL:POW? ──────►│
   │                           │◄── -25.30 ─────────────────│
   │                           │    ... (各測定値取得)        │
   │                           │                            │
   │                           │  DB へ結果を保存            │
   │◄── WS: measurement_result ─│                           │
   │◄── { status: success } ───│                            │
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
docker compose up --build -d

# 停止
docker compose down

# DB データ含め全削除・再構築
docker compose down -v && docker compose up --build -d
```

### 9.3 環境変数 (`backend/.env`)

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| DATABASE_URL | mysql+pymysql://...@mysql:3306/mt8821c_db | MySQL 接続 URL |
| MT8821C_HOST | 192.168.1.100 | MT8821C IP アドレス |
| MT8821C_PORT | 5025 | MT8821C ポート番号 |
| MT8821C_TIMEOUT | 10 | 通信タイムアウト (秒) |

---

## 10. Web UI 機能

### 10.1 画面構成

```
┌─────────────────────────────────────────────────────────────┐
│  ナビゲーションバー: システム名 / MT8821C 接続状態            │
├─────────────────┬───────────────────────────────────────────┤
│  左パネル        │  右パネル                                  │
│  ─────────      │  ─────────                                │
│  接続設定        │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  (IP/接続切断)   │  │TX Pow│ │ EVM  │ │Freq  │ │BLER  │   │
│                 │  │ dBm  │ │  %   │ │Error │ │  %   │   │
│  測定設定一覧    │  └──────┘ └──────┘ └──────┘ └──────┘   │
│  [新規][編集][✕] │                                           │
│                 │  TX Power 履歴グラフ (Chart.js)            │
│  設定フォーム    │                                           │
│  ■ 基本設定     │  ─────────────────────────────────────── │
│    設定名        │  測定履歴テーブル                          │
│    RAT / 複信    │  (日時/設定/TX Pow/EVM/FreqErr/BLER/結果) │
│  ■ RF設定       │                                           │
│    周波数/帯域   │                                           │
│    チャネル番号  │                                           │
│  ■ 電力設定     │                                           │
│    参照/期待電力 │                                           │
│  ■ 測定設定     │                                           │
│    測定回数      │                                           │
│                 │                                           │
│  選択中設定詳細  │                                           │
│  [測定実行]      │                                           │
└─────────────────┴───────────────────────────────────────────┘
```

### 10.2 設定フォームの入力項目

| セクション | 項目 | 入力形式 | 備考 |
|---|---|---|---|
| 基本設定 | 設定名 | テキスト | 必須 |
| 基本設定 | RAT | セレクト | LTE / WCDMA / GSM / NR5G |
| 基本設定 | 複信方式 | セレクト | FDD / TDD (RAT により制限) |
| RF 設定 | 中心周波数 | 数値 (MHz) | 0.1 刻み |
| RF 設定 | 帯域幅 | セレクト (MHz) | 1.4 / 3 / 5 / 10 / 15 / 20 |
| RF 設定 | チャネル番号 | 数値 | 省略可 (EARFCN/UARFCN/ARFCN/NR-ARFCN) |
| 電力設定 | 参照レベル | 数値 (dBm) | 0.5 刻み |
| 電力設定 | 期待送信電力 | 数値 (dBm) | 0.5 刻み |
| 測定設定 | 測定回数 | 数値 | 1〜1000 |

---

## 11. 対応 RAT

| RAT | 規格 | 複信方式 | 測定項目 |
|---|---|---|---|
| LTE | 4G LTE | FDD / TDD | TX Power / EVM / Freq Error / BLER |
| WCDMA | 3G W-CDMA | FDD のみ | TX Power / EVM / Freq Error |
| GSM | 2G GSM/EDGE | FDD のみ | TX Power / Freq Error / BER |
| NR5G | 5G NR | FDD / TDD | TX Power / EVM / Freq Error / BLER |

---

## 12. アクセス先

| 対象 | URL |
|---|---|
| Web UI | http://localhost |
| API ドキュメント (Swagger) | http://localhost:8000/docs |

---

## 13. 変更履歴

| バージョン | 日付 | 内容 |
|---|---|---|
| 1.0.0 | 2026-03-12 | 初版作成 |
| 1.1.0 | 2026-03-12 | 設定パラメータ拡張 (duplex_mode / expected_power / meas_count)、UI改善 |
