# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.

## Tá»•ng Quan Kiáº¿n TrÃºc

```text
Vue 3 + TypeScript + Vite
        |
        | REST API / má»™t WebSocket dÃ¹ng chung
        v
FastAPI backend
        |
        +-- MySQL: user, auth, portfolio, payment, cache nghiá»‡p vá»¥
        +-- DuckDB: daily OHLCV, technical cache, market feature mart
        +-- Redis: optional realtime/cache runtime
        +-- lake/: raw, processed, gold parquet snapshots
        +-- etl/: Extract -> Transform -> Load
```

## ThÃ nh Pháº§n ChÃ­nh

| ThÃ nh pháº§n | MÃ´ táº£ |
|---|---|
| Frontend | Dashboard, danh má»¥c, phÃ¢n tÃ­ch cá»• phiáº¿u, realtime price store dÃ¹ng chung, admin, ETL monitor |
| Backend | API FastAPI, auth JWT, payment SePay, portfolio, stock/market endpoints |
| ETL | Láº¥y dá»¯ liá»‡u giÃ¡, chá»‰ sá»‘, tin tá»©c, cÆ¡ báº£n, transform indicator vÃ  load snapshot |
| Data lake | LÆ°u raw/processed/gold Parquet Ä‘á»ƒ tÃ¡i láº­p snapshot |
| DuckDB | Kho dá»¯ liá»‡u market local cho OHLCV, technical cache vÃ  feature mart |
| MySQL | Dá»¯ liá»‡u app/user/business vÃ  má»™t sá»‘ cache nghiá»‡p vá»¥ |
| Redis | TÃ¹y chá»n, dÃ¹ng cho realtime/cache; náº¿u khÃ´ng cÃ³ backend cÃ³ fallback in-memory |

## YÃªu Cáº§u MÃ´i TrÆ°á»ng

- Node.js 22 hoáº·c tÆ°Æ¡ng thÃ­ch vá»›i Vite 6.
- Python 3.11+.
- MySQL 8 local hoáº·c remote.
- Redis 7 lÃ  tÃ¹y chá»n.
- Windows PowerShell Ä‘Æ°á»£c dÃ¹ng trong cÃ¡c vÃ­ dá»¥ bÃªn dÆ°á»›i.

## CÃ i Äáº·t Láº§n Äáº§u

### 1. CÃ i frontend dependencies

```powershell
cd C:\Users\Lenovo\Downloads\tailadmin-vuejs-1.0.0
npm install
```

### 2. Táº¡o Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend_v2\requirements.txt
```

### 3. Táº¡o file mÃ´i trÆ°á»ng backend

Copy file máº«u:

```powershell
Copy-Item backend_v2\.env.example backend_v2\.env
```

CÃ¡c biáº¿n cáº§n kiá»ƒm tra trong `backend_v2\.env`:

```env
MYSQL_URL=mysql+mysqlconnector://root:YOUR_PASSWORD@localhost/vnstock_data
MYSQL_ASYNC_URL=mysql+aiomysql://root:YOUR_PASSWORD@localhost/vnstock_data
DUCKDB_PATH=lake/warehouse/market.duckdb

JWT_SECRET=change_me_to_a_long_random_string_at_least_32_chars
FRONTEND_URL=http://localhost:5174
BACKEND_URL=http://localhost:8000

REDIS_URL=redis://localhost:6379/0

ETL_SYMBOLS=FPT,VCB,VIC
ETL_LOOKBACK_DAYS=365
ETL_TICK_SOURCE=lake
ETL_RUN_MODE=incremental
ETL_INCREMENTAL_OVERLAP_DAYS=7

VNSTOCK_API_KEY=your_dnse_api_key_here
KAGGLE_API_URL=https://your-kaggle-ngrok.ngrok-free.dev

DNSE_MARKET_BASE_URL=https://openapi.dnse.com.vn
DNSE_MARKET_API_KEY=your_dnse_openapi_key
DNSE_MARKET_API_SECRET=your_dnse_openapi_secret
DNSE_MARKET_BOARD_ID=G1
DNSE_TICK_POLL_INTERVAL_MS=2000
DNSE_TICK_PARQUET_FLUSH_SECONDS=30
DNSE_REALTIME_POLL_WHEN_CLOSED=false
DNSE_REALTIME_CLOSED_HEARTBEAT_SECONDS=300

MARKET_TIMEZONE=Asia/Ho_Chi_Minh
MARKET_MORNING_START=09:00
MARKET_MORNING_END=11:30
MARKET_AFTERNOON_START=13:00
MARKET_AFTERNOON_END=14:45
MARKET_CLOSE_END=15:00
```

Ghi chÃº:

- Backend Ä‘á»c cáº¥u hÃ¬nh tá»« `.env` á»Ÿ root repo vÃ  `backend_v2\.env`; file trong `backend_v2` phÃ¹ há»£p nháº¥t cho runtime backend.
- Frontend dev server Ä‘Ã£ cÃ³ proxy `/api` sang `http://127.0.0.1:8000`, nÃªn thÆ°á»ng khÃ´ng báº¯t buá»™c táº¡o `.env.local`.
- Náº¿u muá»‘n frontend gá»i backend báº±ng URL tuyá»‡t Ä‘á»‘i, táº¡o `.env.local` á»Ÿ root:

```env
VITE_BACKEND_URL=http://127.0.0.1:8000
VITE_BACKEND_POLLING_MS=15000
```

Frontend tá»± Æ°u tiÃªn WebSocket vÃ  chuyá»ƒn sang polling snapshot khi káº¿t ná»‘i realtime khÃ´ng kháº£ dá»¥ng. `VITE_BACKEND_POLLING_MS` Ä‘iá»u chá»‰nh chu ká»³ polling fallback.

### 4. Khá»Ÿi táº¡o MySQL database

Táº¡o database vÃ  báº£ng ná»n táº£ng:

```powershell
mysql -u root -p < backend_v2\init_database.sql
```

Cháº¡y migration:

```powershell
cd backend_v2
..\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
cd ..
```

### 5. Táº¡o dá»¯ liá»‡u market snapshot ban Ä‘áº§u

Backend Ä‘ang theo hÆ°á»›ng strict snapshot: API Ä‘á»c dá»¯ liá»‡u snapshot cÃ³ sáºµn, khÃ´ng tá»± fetch dá»¯ liá»‡u thá»‹ trÆ°á»ng khi startup. VÃ¬ váº­y sau khi cÃ i Ä‘áº·t nÃªn cháº¡y ETL Ã­t nháº¥t má»™t láº§n.

Cháº¡y nhanh vÃ i mÃ£ Ä‘á»ƒ kiá»ƒm tra pipeline:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB --run-mode incremental --tick-source lake --max-workers 2
```

Cháº¡y toÃ n bá»™ VN30 theo máº·c Ä‘á»‹nh:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --run-mode incremental --tick-source lake
```

Káº¿t quáº£ ETL chÃ­nh:

- `market_data.csv`
- `market_data.parquet`
- `lake\raw\...`
- `lake\processed\market_data_<run_id>.parquet`
- `lake\processed\runs\<run_id>.json`
- `lake\silver\market_data\run_id=<run_id>\data.parquet`
- `lake\silver\market_data\latest.parquet`
- `lake\gold\market_features\latest.parquet`
- `lake\manifests\latest_success.json`
- `lake\warehouse\market.duckdb`

## CÃ¡c BÆ°á»›c Khi Khá»Ÿi Äá»™ng Dá»± Ãn

LÃ m theo checklist nÃ y má»—i láº§n má»Ÿ dá»± Ã¡n local:

1. Má»Ÿ terminal táº¡i root repo:

```powershell
cd C:\Users\Lenovo\Downloads\tailadmin-vuejs-1.0.0
```

2. KÃ­ch hoáº¡t Python environment:

```powershell
.\.venv\Scripts\activate
```

3. Äáº£m báº£o MySQL Ä‘ang cháº¡y vÃ  `backend_v2\.env` trá» Ä‘Ãºng `MYSQL_URL`.

4. Náº¿u dÃ¹ng Redis, báº­t Redis:

```powershell
cd backend_v2
docker compose up -d redis
cd ..
```

Náº¿u khÃ´ng dÃ¹ng Redis, backend váº«n cÃ³ thá»ƒ cháº¡y vá»›i fallback in-memory cho má»™t sá»‘ luá»“ng.

5. Cháº¡y migration khi vá»«a pull code má»›i hoáº·c schema thay Ä‘á»•i:

```powershell
cd backend_v2
..\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
cd ..
```

6. Kiá»ƒm tra hoáº·c cáº­p nháº­t snapshot market náº¿u dá»¯ liá»‡u cÅ©:

```powershell
.\.venv\Scripts\python.exe -c "from etl.health import check_etl_health; print(check_etl_health())"
```

Náº¿u health bÃ¡o stale/missing, cháº¡y ETL:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --run-mode incremental --tick-source lake
```

7. Cháº¡y backend:

```powershell
.\.venv\Scripts\python.exe backend_v2\run.py
```

8. Má»Ÿ terminal khÃ¡c vÃ  cháº¡y frontend:

```powershell
npm run dev
```

9. Truy cáº­p:

- Frontend: `http://localhost:5174`
- Backend Swagger: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/api/health`
- Readiness: `http://localhost:8000/api/health/ready`

## CÃ¡ch Cháº¡y Backend

Tá»« root repo:

```powershell
.\.venv\Scripts\python.exe backend_v2\run.py
```

Hoáº·c tá»« thÆ° má»¥c backend:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe run.py
```

Backend máº·c Ä‘á»‹nh cháº¡y táº¡i `http://localhost:8000`.

Cháº¡y backend kÃ¨m ngrok cho webhook SePay local:

```powershell
npm run backend:ngrok
```

TrÆ°á»›c khi dÃ¹ng ngrok, cáº¥u hÃ¬nh cÃ¡c biáº¿n `NGROK_AUTHTOKEN`, `NGROK_DEV_DOMAIN`, `IPN_URL` hoáº·c `SEPAY_IPN_URL` trong `backend_v2\.env`.

## CÃ¡ch Cháº¡y Frontend

```powershell
npm run dev
```

CÃ¡c script frontend:

| Lá»‡nh | MÃ´ táº£ |
|---|---|
| `npm run dev` | Cháº¡y Vite dev server port 5174 |
| `npm run build` | Type-check vÃ  build production |
| `npm run build-only` | Chá»‰ build Vite |
| `npm run type-check` | Kiá»ƒm tra TypeScript/Vue |
| `npm run test:unit` | Cháº¡y unit test má»™t láº§n báº±ng Vitest |
| `npm run test:unit:watch` | Cháº¡y Vitest á»Ÿ watch mode |
| `npm run lint` | Cháº¡y ESLint vÃ  tá»± fix |
| `npm run preview` | Preview báº£n build |

## Realtime GiÃ¡ Cá»• Phiáº¿u TrÃªn Frontend

Frontend quáº£n lÃ½ giÃ¡ hiá»‡n táº¡i báº±ng má»™t luá»“ng realtime táº­p trung, thay vÃ¬ Ä‘á»ƒ tá»«ng trang tá»± má»Ÿ WebSocket hoáº·c tá»± polling:

```text
App.vue
  â””â”€â”€ realtimeManager
        â”œâ”€â”€ WebSocket /api/ws/market
        â”œâ”€â”€ polling fallback /api/stocks/snapshots
        â”œâ”€â”€ symbolRegistry
        â””â”€â”€ stockPriceStore
              â””â”€â”€ cÃ¡c trang Ä‘á»c cÃ¹ng má»™t nguá»“n giÃ¡
```

- `App.vue` khá»Ÿi Ä‘á»™ng vÃ  dá»«ng duy nháº¥t má»™t `realtimeManager` theo vÃ²ng Ä‘á»i á»©ng dá»¥ng.
- Má»—i trang dÃ¹ng `usePriceSubscription(ownerId, symbols)` Ä‘á»ƒ khai bÃ¡o cÃ¡c mÃ£ Ä‘ang cáº§n.
- `symbolRegistry` gá»™p vÃ  Ä‘áº¿m sá»‘ nÆ¡i Ä‘ang dÃ¹ng tá»«ng mÃ£; mÃ£ chá»‰ bá»‹ bá» Ä‘Äƒng kÃ½ khi khÃ´ng cÃ²n trang nÃ o cáº§n.
- Quote tá»« WebSocket Ä‘Æ°á»£c ghi ngay vÃ o `stockPriceStore`. Khi WebSocket lá»—i, manager polling snapshot cho cÃ¡c mÃ£ Ä‘ang active vÃ  tá»± thá»­ káº¿t ná»‘i láº¡i.
- Watchlist cá»§a ngÆ°á»i dÃ¹ng vÃ  danh sÃ¡ch mÃ£ Ä‘ang xem realtime lÃ  hai khÃ¡i niá»‡m riÃªng biá»‡t.
- Chá»‰ giÃ¡ hiá»‡n táº¡i tá»± cáº­p nháº­t khÃ´ng cáº§n reload trang. Lá»‹ch sá»­ giÃ¡, technical, tin tá»©c, sá»± kiá»‡n, tÃ i chÃ­nh vÃ  AI analysis váº«n giá»¯ cÃ¡ch refresh hiá»‡n táº¡i.

CÃ¡c trang Ä‘ang dÃ¹ng luá»“ng giÃ¡ táº­p trung gá»“m Dashboard, Stock Detail, My Portfolio, Portfolio Alerts, Stock Screener vÃ  News Events. Xem mÃ´ táº£ chi tiáº¿t táº¡i `docs/frontend-realtime-architecture.md`.

## Quy Æ¯á»›c Dá»¯ Liá»‡u Frontend

Frontend khÃ´ng hiá»ƒn thá»‹ dá»¯ liá»‡u máº«u trong cÃ¡c mÃ n hÃ¬nh nghiá»‡p vá»¥. Náº¿u backend/API khÃ´ng cÃ³ dá»¯ liá»‡u tháº­t, UI pháº£i dÃ¹ng empty state rÃµ rÃ ng thay vÃ¬ hard-code mÃ£ cá»• phiáº¿u, vá»‹ tháº¿, cáº£nh bÃ¡o hoáº·c notification giáº£.

- `Portfolio Alerts` Ä‘á»c danh má»¥c tá»« `GET /api/portfolio/`. Vá»‹ tháº¿ láº¥y tá»« `quantity` vÃ  `avg_price`; cáº£nh bÃ¡o giÃ¡ Ä‘Æ°á»£c suy ra tá»« `tp_price` vÃ  `sl_price`. Náº¿u danh má»¥c rá»—ng, trang hiá»ƒn thá»‹ empty state vÃ  khÃ´ng render FPT/VCB/HPG/MBB máº«u.
- `Stock Detail` chá»‰ hiá»ƒn thá»‹ `Portfolio Performance` khi user Ä‘ang náº¯m giá»¯ mÃ£ hiá»‡n táº¡i trong portfolio (`quantity > 0`). Náº¿u chÆ°a cÃ³ mÃ£ Ä‘Ã³ trong danh má»¥c, section nÃ y Ä‘Æ°á»£c áº©n vÃ  pháº§n Ä‘á»‹nh giÃ¡ giÃ£n full width.
- Notification menu máº·c Ä‘á»‹nh khÃ´ng cÃ³ thÃ´ng bÃ¡o máº«u. Khi chÆ°a cÃ³ nguá»“n notification tháº­t, dropdown hiá»ƒn thá»‹ `No notifications`.
- CÃ¡c mapping dÃ¹ng chung nhÆ° nhÃ³m ngÃ nh thá»‹ trÆ°á»ng vÃ  default route chi tiáº¿t cá»• phiáº¿u náº±m trong `src/constants/`, khÃ´ng khai bÃ¡o láº·p láº¡i trá»±c tiáº¿p trong tá»«ng page.
- `src/services/dnseApi.ts` lÃ  Ä‘Æ°á»ng gá»i DNSE trá»±c tiáº¿p tá»« browser Ä‘Ã£ Ä‘Æ°á»£c Ä‘Ã¡nh dáº¥u deprecated. Luá»“ng production nÃªn Ä‘i qua backend-backed services nhÆ° `stockBackendApi` hoáº·c `dnseTickSandboxApi`.

## CÃ¡ch Cháº¡y ETL

ETL entrypoint chÃ­nh lÃ :

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl
```

### Cháº¡y incremental

Incremental tá»± tÃ¬m snapshot má»›i nháº¥t trong `lake\processed`, lÃ¹i láº¡i má»™t sá»‘ ngÃ y overlap rá»“i merge vÃ o snapshot hiá»‡n táº¡i.

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB,VIC --run-mode incremental --incremental-overlap-days 7 --tick-source lake
```

Khi `--tick-source lake` hoáº·c `--tick-source auto`, ETL máº·c Ä‘á»‹nh cháº¡y thÃªm phase `dnse_tick_backfill` trÆ°á»›c bÆ°á»›c aggregate tick sang daily OHLCV. Phase nÃ y gá»i DNSE historical trades endpoint cho phiÃªn giao dá»‹ch hoÃ n táº¥t gáº§n nháº¥t, lÆ°u tick theo tá»«ng mÃ£ vÃ o Parquet rá»“i dÃ¹ng cÃ¡c file Ä‘Ã³ cho chart phÃºt/giá» vÃ  tick -> EOD.

Quy táº¯c chá»n phiÃªn:

- Náº¿u cháº¡y sau 15:00 vÃ o ngÃ y giao dá»‹ch, ETL láº¥y phiÃªn cÃ¹ng ngÃ y.
- Náº¿u cháº¡y trÆ°á»›c 15:00, cuá»‘i tuáº§n hoáº·c ngÃ y nghá»‰, ETL láº¥y phiÃªn giao dá»‹ch hoÃ n táº¥t gáº§n nháº¥t trÆ°á»›c Ä‘Ã³.
- Náº¿u file tick Parquet cá»§a mÃ£ Ä‘Ã£ cÃ³ dá»¯ liá»‡u `source=dnse_historical`, ETL bá» qua mÃ£ Ä‘Ã³ Ä‘á»ƒ trÃ¡nh refetch. DÃ¹ng `--force-dnse-tick-backfill` khi cáº§n ghi Ä‘Ã¨.

NÆ¡i lÆ°u tick historical:

```text
backend_v2\data_lake\ticks\YYYY-MM-DD\{SYMBOL}.parquet
```

Cháº¡y riÃªng DNSE historical tick backfill cho phiÃªn gáº§n nháº¥t:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_dnse_ticks --symbols FPT,VCB,VIC --latest-session
```

Cháº¡y cho má»™t ngÃ y cá»¥ thá»ƒ:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_dnse_ticks --symbols FPT,VCB,VIC --session-date 2026-06-09
```

Ã‰p refetch vÃ  ghi Ä‘Ã¨ file Ä‘Ã£ cÃ³:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_dnse_ticks --symbols FPT --session-date 2026-06-09 --force
```

Trong metadata ETL, phase nÃ y ghi cÃ¡c chá»‰ sá»‘:

- `dnse_tick_backfilled_symbols`
- `dnse_tick_existing_symbols`
- `dnse_tick_empty_symbols`
- `dnse_tick_backfill_session_date`

Backend `/api/stocks/{symbol}/intraday` vÃ  `/api/stocks/{symbol}/ticks` cÃ³ fallback Ä‘á»c tick Parquet phiÃªn gáº§n nháº¥t khi cache realtime rá»—ng. VÃ¬ váº­y sau giá» giao dá»‹ch váº«n cÃ³ thá»ƒ má»Ÿ chart phÃºt/giá» cá»§a phiÃªn gáº§n nháº¥t náº¿u tick backfill Ä‘Ã£ cháº¡y thÃ nh cÃ´ng.

### Cháº¡y full theo khoáº£ng ngÃ y

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB,VIC --start-date 2025-04-01 --end-date 2026-04-01 --run-mode full
```

### Cháº¡y backfill má»™t khoáº£ng ngÃ y

Backfill phÃ¹ há»£p khi cáº§n cáº­p nháº­t láº¡i má»™t Ä‘oáº¡n dá»¯ liá»‡u trong snapshot hiá»‡n cÃ³.

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT --start-date 2026-04-20 --end-date 2026-04-28 --run-mode backfill --max-workers 2
```

### Cháº¡y nhanh khi chá»‰ cáº§n giÃ¡ vÃ  technical

Táº¯t bá»›t nguá»“n náº·ng nhÆ° fundamental hoáº·c Google News:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB --run-mode incremental --disable-fundamental --disable-google-news --max-workers 2
```

### Chá»‰ ghi file, bá» qua MySQL hoáº·c DuckDB

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB --disable-mysql-load --disable-duckdb-market-load
```

### CÃ¡c tham sá»‘ ETL hay dÃ¹ng

| Tham sá»‘ | MÃ´ táº£ |
|---|---|
| `--symbols FPT,VCB` | Danh sÃ¡ch mÃ£, phÃ¢n tÃ¡ch báº±ng dáº¥u pháº©y |
| `--start-date YYYY-MM-DD` | NgÃ y báº¯t Ä‘áº§u output |
| `--end-date YYYY-MM-DD` | NgÃ y káº¿t thÃºc output |
| `--run-mode full` | Cháº¡y láº¡i toÃ n bá»™ khoáº£ng ngÃ y Ä‘Æ°á»£c chá»‰ Ä‘á»‹nh |
| `--run-mode incremental` | Cáº­p nháº­t dá»±a trÃªn snapshot má»›i nháº¥t |
| `--run-mode backfill` | Ghi Ä‘Ã¨/merge má»™t khoáº£ng ngÃ y vÃ o snapshot má»›i nháº¥t |
| `--incremental-overlap-days 7` | Sá»‘ ngÃ y overlap khi incremental |
| `--max-workers 6` | Sá»‘ worker extract song song |
| `--tick-source lake` | Nguá»“n tick Ä‘á»ƒ aggregate EOD: `lake`, `redis`, `auto` |
| `--disable-dnse-tick-backfill` | Bá» qua phase kÃ©o DNSE historical ticks trÆ°á»›c khi aggregate tick |
| `--dnse-tick-session-date YYYY-MM-DD` | KÃ©o tick DNSE cho phiÃªn cá»¥ thá»ƒ thay vÃ¬ phiÃªn hoÃ n táº¥t gáº§n nháº¥t |
| `--force-dnse-tick-backfill` | Refetch vÃ  ghi Ä‘Ã¨ file tick Parquet Ä‘Ã£ cÃ³ |
| `--disable-fundamental` | KhÃ´ng extract bÃ¡o cÃ¡o tÃ i chÃ­nh |
| `--disable-google-news` | KhÃ´ng extract Google News |
| `--disable-mysql-load` | KhÃ´ng load cache vÃ o MySQL |
| `--disable-duckdb-market-load` | KhÃ´ng load market warehouse vÃ o DuckDB |
| `--no-merge-with-latest` | KhÃ´ng merge incremental/backfill vá»›i snapshot má»›i nháº¥t |

## Data Lake Publish Model

ETL ghi immutable run artifacts truoc, sau do moi publish snapshot cho app doc. Mot run chi duoc xem la serving-ready khi:

1. Transform tao dataset thanh cong.
2. Final merged dataset vuot qua publish quality gate.
3. Processed, silver, gold va DuckDB/MySQL load hoan tat.
4. `lake\manifests\latest_success.json` duoc cap nhat atomic.

Mo hinh nay giup tranh tinh huong mot snapshot loi bi app doc nham la latest. Khi quality gate fail, run metadata se ghi `failed`, nhung manifest latest cu van duoc giu nguyen.

Current compatible paths:

| Layer/path | Vai tro |
|---|---|
| `lake\raw` | Raw extractor files theo source/run |
| `lake\processed` | Legacy processed snapshots, giu de tuong thich script cu |
| `lake\silver\market_data` | Normalized market data theo `run_id` va `latest.parquet` |
| `lake\gold\market_features` | Feature mart cho AI/backtest/API |
| `lake\manifests\latest_success.json` | Serving pointer cho snapshot thanh cong moi nhat |
| `lake\warehouse\market.duckdb` | Local analytical warehouse va AI job/result store |

Quality gate hien check cac loi schema/duplicate/OHLC/volume/close, symbol coverage va outlier ratio. Mac dinh yeu cau it nhat 95% so ma ky vong co mat trong dataset va outlier ratio khong qua 5%.

## Scheduler ETL

Kiá»ƒm tra cÃ¡c job sáº½ Ä‘Äƒng kÃ½:

```powershell
.\.venv\Scripts\python.exe -m etl.scheduler --dry-run
```

Cháº¡y scheduler Ä‘á»™c láº­p:

```powershell
.\.venv\Scripts\python.exe -m etl.scheduler
```

Lá»‹ch máº·c Ä‘á»‹nh:

| Job | Lá»‹ch | MÃ´ táº£ |
|---|---:|---|
| `etl-daily-full` | 15:20 Mon-Fri | Cháº¡y ETL incremental |
| `etl-cache-refresh` | 15:30 Mon-Fri | Refresh cache sau ETL |
| `etl-weekly-fundamental` | 00:00 Sunday | Refresh dá»¯ liá»‡u cÆ¡ báº£n |
| `etl-health-check` | 5 phÃºt/láº§n | Kiá»ƒm tra freshness vÃ  lá»—i ETL |

Backend web hiá»‡n khÃ´ng nÃªn Ä‘Æ°á»£c xem lÃ  nÆ¡i tá»± Ä‘á»™ng táº¡o snapshot market khi startup. ÄÆ°á»ng ghi dá»¯ liá»‡u market Ä‘Æ°á»£c khuyáº¿n nghá»‹ lÃ  CLI ETL, scheduler Ä‘á»™c láº­p hoáº·c admin ETL trigger.

## DuckDB VÃ  Market Feature Mart

ÄÆ°á»ng dáº«n máº·c Ä‘á»‹nh:

```text
lake/warehouse/market.duckdb
```

Inspect mart:

```powershell
.\.venv\Scripts\python.exe -m etl.inspect_duckdb_market_mart
```

Backfill mart tá»« Parquet snapshot:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_duckdb_market_features --parquet lake/gold/market_features/latest.parquet --run-id backfill-latest
```

Backfill káº¿t quáº£ thá»±c táº¿ cho cÃ¡c láº§n phÃ¢n tÃ­ch AI:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_ai_prediction_outcomes --horizon-trading-days 5
```

### AI Analysis Ledger Trong DuckDB

Ket qua AI duoc luu trong cung DuckDB warehouse:

```text
lake/warehouse/market.duckdb
```

Backend se tao schema DuckDB khi startup. Sau khi co thay doi schema moi, nen restart backend de cac bang moi nhu `ai_generation_jobs` duoc tao bang `CREATE TABLE IF NOT EXISTS`.

Bang chinh:

| Bang | Noi dung |
|---|---|
| `ai_generation_jobs` | Trang thai job async: `queued`, `running`, `success`, `failed` |
| `ai_analysis_runs` | Metadata cua moi lan phan tich: symbol, status, decision, confidence, model version, error |
| `ai_analysis_payloads` | Input/output day du: context, prompt, Kaggle response, raw model output, normalized output |
| `ai_prediction_outcomes` | Ket qua doi chieu sau nay cho backtest/evaluation |

Mapping input/output trong `ai_analysis_payloads`:

| Cot | Y nghia |
|---|---|
| `request_context_json` | Market context dua vao model |
| `prompt_text` | Prompt thuc te gui sang Trading-R1/Kaggle API |
| `kaggle_response_json` | JSON response tu API |
| `raw_output` | Raw text output cua model |
| `normalized_output_json` | Ket qua da parse/normalize de frontend hien thi |

Inspect nhanh so dong:

```powershell
.\.venv\Scripts\python.exe -c "import duckdb; c=duckdb.connect('lake/warehouse/market.duckdb', read_only=True); print(c.execute('SELECT COUNT(*) FROM ai_analysis_runs').fetchone()); print(c.execute('SELECT COUNT(*) FROM ai_analysis_payloads').fetchone()); print(c.execute('SELECT COUNT(*) FROM ai_generation_jobs').fetchone())"
```

Xem 5 lan phan tich moi nhat:

```powershell
.\.venv\Scripts\python.exe -c "import duckdb; c=duckdb.connect('lake/warehouse/market.duckdb', read_only=True); print(c.execute('SELECT analysis_id, symbol, status, decision, confidence, created_at, completed_at FROM ai_analysis_runs ORDER BY created_at DESC LIMIT 5').fetchall())"
```

## Admin ETL Monitor

Trong Admin Dashboard cÃ³ tab ETL Monitor Ä‘á»ƒ xem:

- ETL health vÃ  freshness.
- Run gáº§n nháº¥t, sá»‘ dÃ²ng, sá»‘ mÃ£, thá»i gian cháº¡y.
- Quality summary.
- Load targets: Parquet, gold layer, DuckDB, MySQL cache.
- Lá»‹ch sá»­ cÃ¡c run.
- NÃºt trigger ETL thá»§ cÃ´ng cho admin.

Endpoint ETL:

```text
GET  /api/etl/status
GET  /api/etl/runs?limit=10
GET  /api/etl/health
POST /api/etl/trigger
```

`POST /api/etl/trigger` yÃªu cáº§u admin token vÃ  cÃ³ rate limit.

## API ChÃ­nh

Health:

```text
GET /api/health/live
GET /api/health/ready
GET /api/health
```

Auth:

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
PUT  /api/auth/profile
PUT  /api/auth/password
```

Stocks/Market:

```text
GET /api/stocks
GET /api/stocks/snapshots
GET /api/stocks/{symbol}/overview
GET /api/stocks/{symbol}/history
GET /api/stocks/{symbol}/intraday
GET /api/stocks/{symbol}/ticks
GET /api/stocks/{symbol}/technical
GET /api/stocks/{symbol}/financials
GET /api/market-indices
GET /api/market-indices/{index_symbol}/history
GET /api/news
GET /api/google-news
GET /api/events
WS  /api/ws/market
```

DNSE tick sandbox:

```text
GET /api/dnse/ticks/status
GET /api/dnse/ticks/latest?symbols=FPT,VCB,VIC
GET /api/dnse/ticks/debug?symbol=FPT
```

Trang test frontend:

```text
http://localhost:5174/dnse-ticks
```

Trang nay chi dung de test latest trade/tick read-only tu DNSE. Neu chua cau hinh `DNSE_MARKET_API_KEY` va `DNSE_MARKET_API_SECRET`, backend se tra `not_configured` de frontend hien thi loi cau hinh ro rang.

Backend co market-hours guard cho DNSE realtime:

- Trong phien `09:00-11:30`, `13:00-14:45`, va phien ATC/closing den `15:00`: `/api/dnse/ticks/latest` poll DNSE binh thuong.
- Tick hop le duoc giu trong Redis hoac in-memory fallback va duoc flush atomic xuong `backend_v2/data_lake/ticks/YYYY-MM-DD/{symbol}.parquet` theo chu ky `DNSE_TICK_PARQUET_FLUSH_SECONDS`.
- Ngoai phien, nghi trua, hoac cuoi tuan: endpoint khong poll DNSE nua ma doc last-known tick theo thu tu cache -> Parquet. Response giu `status=market_closed`, them `is_stale=true`, `data_source=cached_last_tick`, `missing_symbols`, kem `market_session` va `next_open_at`.
- Frontend sandbox van hien tick da luu neu co, kem canh bao stale mau vang va giam nhip heartbeat theo `DNSE_REALTIME_CLOSED_HEARTBEAT_SECONDS`.
- Neu chay local khong co Redis, cac tick trong in-memory co the mat sau backend restart neu chua kip flush Parquet.
- Neu can test DNSE ngoai phien, dung `/api/dnse/ticks/debug?symbol=FPT` hoac tam thoi set `DNSE_REALTIME_POLL_WHEN_CLOSED=true`.
- Guard nay giup tranh viec gia cu tu DNSE bi hien thi nhu realtime tick moi.

Analysis:

```text
POST /api/analysis/{symbol}/generate
```

Portfolio:

```text
GET    /api/portfolio/
POST   /api/portfolio/
PUT    /api/portfolio/{symbol}
DELETE /api/portfolio/{symbol}
```

Payment:

```text
GET  /api/payment/premium-info
POST /api/payment/create-checkout
GET  /api/payment/subscription-status
POST /api/payment/sepay/webhook
```

Admin:

```text
GET    /api/admin/sales-stats
GET    /api/admin/users
GET    /api/admin/user-portfolios
PUT    /api/admin/users/{user_id}/role
PUT    /api/admin/users/{user_id}/lock
PUT    /api/admin/users/{user_id}/unlock
GET    /api/admin/promotions
POST   /api/admin/promotions
PUT    /api/admin/promotions/{promotion_id}
PATCH  /api/admin/promotions/{promotion_id}/status
DELETE /api/admin/promotions/{promotion_id}
GET    /api/admin/flash-sales
POST   /api/admin/flash-sales
PUT    /api/admin/flash-sales/{flash_sale_id}
PATCH  /api/admin/flash-sales/{flash_sale_id}/status
DELETE /api/admin/flash-sales/{flash_sale_id}
```

## Cáº¥u TrÃºc ThÆ° Má»¥c

```text
tailadmin-vuejs-1.0.0/
â”œâ”€â”€ src/                         # Frontend Vue
â”‚   â”œâ”€â”€ views/
â”‚   â”œâ”€â”€ components/
â”‚   â”œâ”€â”€ composables/             # usePriceSubscription, useStockData
â”‚   â”œâ”€â”€ realtime/                # manager vÃ  registry symbol
â”‚   â”œâ”€â”€ services/
â”‚   â”œâ”€â”€ stores/                  # shared current-price store
â”‚   â”œâ”€â”€ test/                    # Vitest setup
â”‚   â””â”€â”€ router/
â”œâ”€â”€ backend_v2/                  # FastAPI backend
â”‚   â”œâ”€â”€ alembic/
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ api/
â”‚   â”‚   â”œâ”€â”€ routes/
â”‚   â”‚   â”œâ”€â”€ services/
â”‚   â”‚   â””â”€â”€ database/
â”‚   â”œâ”€â”€ init_database.sql
â”‚   â”œâ”€â”€ requirements.txt
â”‚   â””â”€â”€ run.py
â”œâ”€â”€ etl/                         # ETL pipeline
â”‚   â”œâ”€â”€ extract/
â”‚   â”œâ”€â”€ transform/
â”‚   â”œâ”€â”€ run_etl.py
â”‚   â”œâ”€â”€ scheduler.py
â”‚   â””â”€â”€ load_to_duckdb.py
â”œâ”€â”€ lake/                        # Data lake local
â”‚   â”œâ”€â”€ raw/
â”‚   â”œâ”€â”€ processed/
â”‚   â”œâ”€â”€ gold/
â”‚   â””â”€â”€ warehouse/
â”œâ”€â”€ logs/
â”œâ”€â”€ package.json
â””â”€â”€ vite.config.ts
```

## Kiá»ƒm Tra VÃ  Build

Frontend:

```powershell
npm run test:unit
npm run type-check
npm run build-only
```

Unit test frontend bao phá»§ registry symbol, cáº­p nháº­t shared price store, lifecycle/fallback cá»§a realtime manager, DNSE WebSocket service, Portfolio Alerts khÃ´ng dÃ¹ng dá»¯ liá»‡u máº«u, Stock Detail chá»‰ hiá»‡n Portfolio Performance khi user cÃ³ holding, vÃ  cÃ¡c constants dÃ¹ng chung.

Backend/ETL compile:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Backend smoke test:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.main import app; print(app.title)"
```

Health smoke test:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from fastapi.testclient import TestClient; from src.main import app; c=TestClient(app); print(c.get('/api/health/live').json())"
```

## Lá»—i ThÆ°á»ng Gáº·p

### Frontend gá»i API khÃ´ng Ä‘Æ°á»£c

- Äáº£m báº£o backend Ä‘ang cháº¡y á»Ÿ `http://localhost:8000`.
- Náº¿u dÃ¹ng `VITE_BACKEND_URL`, kiá»ƒm tra file `.env.local`.
- Náº¿u khÃ´ng dÃ¹ng `VITE_BACKEND_URL`, Vite dev proxy sáº½ chuyá»ƒn `/api` sang backend.

### Backend bÃ¡o lá»—i database

- Kiá»ƒm tra MySQL Ä‘ang cháº¡y.
- Kiá»ƒm tra `MYSQL_URL` vÃ  `MYSQL_ASYNC_URL`.
- Cháº¡y láº¡i migration:

```powershell
cd backend_v2
..\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
cd ..
```

### API market bÃ¡o khÃ´ng cÃ³ snapshot

Cháº¡y ETL Ä‘á»ƒ táº¡o snapshot:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --run-mode incremental --tick-source lake
```

### ETL bá»‹ cháº­m

- Giáº£m sá»‘ mÃ£ báº±ng `--symbols`.
- Táº¯t nguá»“n náº·ng báº±ng `--disable-fundamental --disable-google-news`.
- Giáº£m worker náº¿u bá»‹ rate limit: `--max-workers 2`.

### Redis khÃ´ng cháº¡y

Redis lÃ  optional cho local dev. Náº¿u muá»‘n báº­t:

```powershell
cd backend_v2
docker compose up -d redis
cd ..
```

## Ghi ChÃº Production

- Äá»•i `JWT_SECRET` trÆ°á»›c khi deploy.
- Cáº¥u hÃ¬nh CORS báº±ng `FRONTEND_URL`.
- Cháº¡y Alembic migration trÆ°á»›c khi deploy.
- Sau khi schema á»•n Ä‘á»‹nh, cÃ¢n nháº¯c Ä‘áº·t `DB_LEGACY_AUTO_DDL=false`.
- KhÃ´ng public admin ETL trigger trá»±c tiáº¿p ngoÃ i internet.
- Backup `lake\processed`, `lake\gold`, `lake\warehouse` vÃ  MySQL.
- Cháº¡y ETL scheduler nhÆ° process riÃªng náº¿u cáº§n cáº­p nháº­t dá»¯ liá»‡u Ä‘á»‹nh ká»³.
