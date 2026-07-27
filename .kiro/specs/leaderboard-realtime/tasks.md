# Implementation Plan: Leaderboard Realtime

## Overview

Triển khai hệ thống leaderboard realtime cho crypto DEX trading contest. Các task được chia theo layer: core logic trước, service layer, API endpoints, rồi frontend.

## Tasks

- [x] 1. Tạo LeaderboardCalculator service
  - Tạo file `backend_v2/src/services/leaderboard_calculator.py` với dataclass `LeaderboardRow`, `LeaderboardSnapshot`
  - Implement `compute_snapshot(contest, participants, prices, sort_by)` tính equity/PnL/ROI/volume cho từng participant
  - Implement `compute_single_row(contest, participant, prices)` tính cho một participant
  - Đảm bảo ROI = 0 khi initial_equity = 0 (không raise exception)
  - Đảm bảo symbol thiếu trong prices dict → position_value = 0 (không raise KeyError)
  - Sort rows giảm dần theo sort_by, gán rank liên tục từ 1
  - Lọc participant không có TradingAccount ra khỏi kết quả
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.2, 2.3_

- [x] 2. Thêm hypothesis vào requirements.txt
  - Thêm `hypothesis>=6.0.0` vào `backend_v2/requirements.txt`
  - _Requirements: (testing dependency)_

- [x] 3. Viết unit tests và property-based tests cho LeaderboardCalculator
  - Test equity = cash + position_value với các trường hợp: chỉ cash, chỉ position, cả hai
  - Test ROI không crash khi initial_equity = 0
  - Test symbol thiếu giá → không crash, position_value = 0
  - Test sort equity/pnl/roi đều cho thứ tự giảm dần đúng
  - Test rank là dãy 1..N liên tục, không duplicate
  - Test participant không có account bị lọc ra
  - **PBT**: `@given` equity luôn >= 0 với mọi combination prices/quantities hợp lệ — **Property 1**
  - **PBT**: `@given` rank là dãy `range(1, N+1)` với mọi số lượng participants — **Property 2**
  - **PBT**: `@given` rows sort giảm dần theo sort_by với mọi sort_by trong {equity, pnl, roi} — **Property 3**
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 2.2, 2.3_

- [x] 4. Tạo Pydantic schemas cho leaderboard API
  - Tạo `LeaderboardRowPublic` schema trong `backend_v2/src/schemas/leaderboard.py`
  - Tạo `LeaderboardRowAdmin(LeaderboardRowPublic)` với thêm `user_id`, `participant_status`
  - Tạo `LeaderboardSnapshotResponse` schema với `contest_id`, `sort_by`, `updated_at`, `rows`
  - _Requirements: 4.5, 5.2, 5.3_

- [x] 5. Mở rộng BinanceRealtimeService để support price update callbacks
  - Thêm `register_price_listener(callback: Callable)` vào `BinanceRealtimeService`
  - Gọi tất cả registered callbacks trong `_process_raw_message` khi có ticker event mới
  - Callbacks được gọi async với `asyncio.gather` (không block stream loop)
  - _Requirements: 3.2_

- [x] 6. Tạo LeaderboardBroadcastService
  - Tạo file `backend_v2/src/services/leaderboard_broadcast.py`
  - Implement `__init__` với: realtime_service, db_session_factory, throttle_seconds=1.0, participant_cache_ttl=5.0
  - Implement `start()` / `stop()` lifecycle (asyncio tasks)
  - Implement client registry: `_clients: dict[str, set[WebSocket]]` theo contest_id
  - Implement throttle logic: broadcast tối đa 1 lần/giây/contest
  - Implement participant cache với TTL 5 giây per contest
  - Implement `handle_client(websocket, contest_id, is_admin)`: accept, send snapshot, listen messages, cleanup on disconnect
  - Implement xử lý message `set_sort` từ client: re-sort và gửi lại
  - Implement filter user_id khỏi response khi is_admin=False
  - Implement error response và graceful close khi contest không tồn tại
  - Tích hợp với BinanceRealtimeService qua callback đã tạo ở task 5
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 5.2, 5.3, 5.4, 6.2, 6.3, 6.4, 6.5_

- [x] 7. Tạo LeaderboardRouter (FastAPI)
  - Tạo file `backend_v2/src/routes/leaderboard.py`
  - Implement `GET /api/leaderboard/{contest_id}` với query param `sort_by`
  - REST endpoint dùng `RealtimeMarketCache.get_prices()`, fallback sang `get_latest_prices()`
  - Implement `WS /api/leaderboard/ws/{contest_id}` với query param `sort_by` và `admin_token`
  - Validate `admin_token` JWT và resolve `is_admin` flag
  - Route delegation sang `LeaderboardBroadcastService.handle_client()`
  - Trả HTTP 404 khi contest không tồn tại (REST), error message + close khi WS
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.4, 6.1, 6.5_

- [x] 8. Tích hợp vào app lifespan và main.py
  - Cập nhật `backend_v2/src/jobs.py`: khởi tạo `LeaderboardBroadcastService` trong `build_lifespan`, start/stop cùng với realtime service
  - Cập nhật `backend_v2/src/main.py`: import và register `leaderboard_router`
  - Đảm bảo `LeaderboardBroadcastService` nhận đúng reference tới `BinanceRealtimeService` đã start
  - _Requirements: 3.1, 3.2_

- [ ] 9. Checkpoint — Backend integration tests
  - Ensure all backend tests pass, ask the user if questions arise.

  - [ ] 9.1 Viết integration tests cho REST endpoint
    - Test `GET /api/leaderboard/{contest_id}` với `TestClient`: response có đúng structure, `rows` sorted theo `sort_by`
    - Test HTTP 404 khi contest không tồn tại
    - Test field `updated_at` có mặt trong response (ISO8601 UTC)
    - Test `user_id` không xuất hiện trong public response
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [ ]* 9.2 Viết property-based test cho throttle guarantee
    - **Property 6: Throttle Guarantee** — emit nhiều price events liên tiếp trong khoảng `throttle_seconds`, đảm bảo broadcast count ≤ 1
    - **Validates: Requirements 3.3**

  - [ ] 9.3 Viết integration tests cho WebSocket endpoint
    - Test WS connect → nhận `leaderboard_snapshot` ngay lập tức (type, contest_id, rows, updated_at đều có mặt)
    - Test WS gửi `set_sort` message → nhận snapshot mới với sort order thay đổi
    - Test WS với contest không tồn tại → nhận `{"type":"error","message":"Contest not found"}` rồi connection đóng
    - Test WS gửi `sort_by` không hợp lệ → nhận error message nhưng connection vẫn mở
    - _Requirements: 3.1, 3.5, 6.4, 6.5_

  - [ ] 9.4 Viết integration tests cho admin WebSocket
    - Test WS với `admin_token` hợp lệ → response rows có `user_id` và `participant_status`
    - Test WS với `admin_token` invalid → nhận `{"type":"error","message":"Unauthorized"}`, connection đóng
    - Test `user_id` không xuất hiện khi không có admin_token
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 10. Cập nhật frontend types và API service
  - [ ] 10.1 Thêm leaderboard types vào `src/types/crypto.ts`
    - Thêm `export type LeaderboardSortBy = 'equity' | 'pnl' | 'roi'`
    - Thêm `LeaderboardWsMessage` union type cho `leaderboard_snapshot`, `leaderboard_update`, `error` message shapes từ server
    - Thêm `LeaderboardClientMessage` type cho `set_sort` message từ client
    - _Requirements: 7.1, 7.4_

  - [ ] 10.2 Thêm `fetchLeaderboardSnapshot` vào `src/services/cryptoContestApi.ts`
    - Thêm hàm `fetchLeaderboardSnapshot(contestId: string, sortBy?: LeaderboardSortBy): Promise<LeaderboardRow[]>` gọi `GET /api/leaderboard/{id}?sort_by=...`
    - Map response từ backend (snake_case) sang frontend types (camelCase): `trade_count → tradeCount`, `last_trade → lastTrade`, `updated_at → updatedAt`
    - Hàm cũ `fetchContestLeaderboard` giữ nguyên để không breaking change
    - _Requirements: 7.6_

- [ ] 11. Tạo composable `useLeaderboardRealtime`
  - [ ] 11.1 Tạo file `src/composables/useLeaderboardRealtime.ts`
    - Implement composable nhận `contestId: Ref<string>` làm tham số
    - Expose reactive: `rows: Ref<LeaderboardRow[]>`, `sortBy: Ref<LeaderboardSortBy>`, `status: Ref<'connecting' | 'connected' | 'error'>`
    - Expose method: `setSortBy(sort: LeaderboardSortBy): void`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 11.2 Implement WebSocket lifecycle trong composable
    - `connect()`: khởi tạo `WebSocket` tới `${wsBase}/api/leaderboard/ws/${contestId.value}?sort_by=${sortBy.value}`
    - `onmessage`: parse JSON, update `rows` khi type là `leaderboard_snapshot` hoặc `leaderboard_update`, set `status = 'connected'`
    - `onerror` / `onclose`: set `status = 'error'`, trigger fallback polling
    - `onUnmounted`: gọi `socket.close()` để cleanup
    - _Requirements: 7.1, 7.2, 7.5_

  - [ ] 11.3 Implement fallback REST polling trong composable
    - Khi WS `status === 'error'`, bắt đầu `setInterval` polling mỗi 10 giây dùng `fetchLeaderboardSnapshot`
    - Hủy interval khi WS reconnect thành công hoặc component unmount
    - _Requirements: 7.6_

  - [ ]* 11.4 Viết unit tests cho `useLeaderboardRealtime` composable
    - Test: khi `onmessage` nhận `leaderboard_snapshot` → `rows` được update, `status === 'connected'`
    - Test: khi WS error → `status === 'error'`, fallback polling được kích hoạt
    - Test: `setSortBy` gửi đúng message `{"type":"set_sort","sort_by":"roi"}` qua socket
    - Test: `onUnmounted` → `socket.close()` được gọi
    - _Requirements: 7.1, 7.2, 7.5, 7.6_

- [ ] 12. Cập nhật `ContestLeaderboard.vue` và `LeaderboardTable.vue`
  - [ ] 12.1 Cập nhật `ContestLeaderboard.vue` dùng composable mới
    - Replace `fetchContestLeaderboard` bằng `useLeaderboardRealtime(contestId)` composable
    - Remove `loading` + `loadError` refs dùng REST; dùng `status` từ composable để hiển thị state
    - Xóa `onMounted` async fetch, composable tự quản lý lifecycle
    - _Requirements: 7.1, 7.2_

  - [ ] 12.2 Thêm connection status indicator vào `ContestLeaderboard.vue`
    - Hiển thị badge nhỏ cạnh tiêu đề "Leaderboard": `connecting` (màu vàng), `connected` (màu xanh lá, nhấp nháy "LIVE"), `error` (màu đỏ, "Polling")
    - _Requirements: 7.3_

  - [ ] 12.3 Thêm sort controls vào `ContestLeaderboard.vue`
    - Thêm 3 nút hoặc tabs (Equity / PnL / ROI) gọi `setSortBy()` từ composable khi click
    - Active sort criterion được highlight
    - Truyền `sortBy` xuống `LeaderboardTable` qua prop
    - _Requirements: 7.4_

  - [ ] 12.4 Cập nhật `LeaderboardTable.vue` để nhận `sortBy` prop và hiển thị sort indicator
    - Thêm prop `sortBy: LeaderboardSortBy` (default `'equity'`)
    - Các column header Equity, PnL, ROI hiển thị mũi tên ▼ khi đang là active sort column
    - Bỏ `sorted` computed trong component — việc sort do server thực hiện, component chỉ render đúng thứ tự
    - _Requirements: 7.4_

- [ ] 13. Checkpoint — Đảm bảo toàn bộ flow hoạt động end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- `LeaderboardCalculator` là pure Python, không async, dễ test với hypothesis.
- Không cần migration DB — feature này chỉ đọc dữ liệu, không thêm bảng mới.
- `BinanceRealtimeService` đã được mở rộng ở task 5 (backward compatible).
- Endpoint mới `/api/leaderboard/...` tách biệt với `/api/crypto/contests/{id}/leaderboard` hiện tại — cả hai cùng tồn tại. Endpoint cũ có thể deprecated dần.
- Admin token qua query param sẽ lộ trong access log. TODO: xem xét nâng cấp lên initial handshake message sau.
- Frontend fallback polling dùng `GET /api/leaderboard/{id}` (endpoint mới với realtime price), không dùng endpoint cũ.
- Tasks 10-12 là frontend, có thể làm song song với task 9 (backend tests) vì chúng độc lập nhau.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["9.1", "9.3", "10.1"] },
    { "id": 1, "tasks": ["9.2", "9.4", "10.2"] },
    { "id": 2, "tasks": ["11.1"] },
    { "id": 3, "tasks": ["11.2", "11.3"] },
    { "id": 4, "tasks": ["11.4", "12.1"] },
    { "id": 5, "tasks": ["12.2", "12.3"] },
    { "id": 6, "tasks": ["12.4"] }
  ]
}
```
