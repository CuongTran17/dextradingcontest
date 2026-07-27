# Requirements Document

## Introduction

Feature này nâng cấp hệ thống leaderboard hiện tại của crypto DEX trading contest lên thời gian thực. Thay vì chỉ cung cấp REST endpoint tĩnh (snapshot một lần), hệ thống sẽ push bảng xếp hạng cập nhật liên tục qua WebSocket mỗi khi giá Binance thay đổi. Cả Admin và User đều có thể theo dõi, với Admin nhận thêm thông tin chi tiết.

---

## Requirements

### Requirement 1: Tính toán Equity, PnL, ROI theo giá realtime

**User Story:** Là một user tham gia contest, tôi muốn thấy equity/PnL/ROI của mình và các người chơi khác được tính theo giá Binance hiện tại, không phải giá cũ.

#### Acceptance Criteria

1.1 Equity của mỗi participant = `cash_balance + sum(position_quantity × current_price)` trong đó `current_price` lấy từ `RealtimeMarketCache`. Nếu cache rỗng, fallback sang Binance REST API.

1.2 PnL = `equity − initial_equity` (có thể âm).

1.3 ROI = `(pnl / initial_equity) × 100` (đơn vị %). Khi `initial_equity = 0`, ROI = 0 (không raise exception).

1.4 Volume = tổng `executed_notional` của tất cả orders có `status = "filled"`.

1.5 Nếu một symbol trong positions không có giá trong cache, giá trị position đó tính bằng 0 (position_value = 0, không raise KeyError).

1.6 Participant chưa có `TradingAccount` không xuất hiện trong leaderboard.

---

### Requirement 2: Sort ranking theo nhiều tiêu chí

**User Story:** Là một user xem leaderboard, tôi muốn sắp xếp bảng xếp hạng theo equity, PnL, hoặc ROI để so sánh hiệu quả giao dịch theo các góc nhìn khác nhau.

#### Acceptance Criteria

2.1 Hệ thống hỗ trợ 3 tiêu chí sort: `equity` (default), `pnl`, `roi`.

2.2 Rows được sort giảm dần (descending) theo tiêu chí được chọn. Người có giá trị cao nhất có rank = 1.

2.3 Rank là dãy số nguyên liên tục từ 1 đến N (không có gap, không có duplicate).

2.4 User có thể đổi sort criterion trong khi đang xem WebSocket live feed (gửi message `{"type":"set_sort","sort_by":"roi"}`). Server re-sort và gửi lại snapshot ngay lập tức.

2.5 Sort criterion được truyền qua query parameter khi kết nối WebSocket: `/api/leaderboard/ws/{contest_id}?sort_by=roi`.

---

### Requirement 3: Cập nhật realtime qua WebSocket push

**User Story:** Là một user đang xem leaderboard, tôi muốn thứ hạng tự động cập nhật khi giá thay đổi mà không cần reload trang.

#### Acceptance Criteria

3.1 Server cung cấp WebSocket endpoint tại `/api/leaderboard/ws/{contest_id}`. Client kết nối và nhận bảng xếp hạng ngay lập tức (snapshot đầu tiên có `"type": "leaderboard_snapshot"`).

3.2 Mỗi khi `BinanceRealtimeService` nhận price update mới, `LeaderboardBroadcastService` tính lại và push leaderboard mới xuống tất cả clients đang kết nối cho contest đó. Message type là `"leaderboard_update"`.

3.3 Broadcast bị throttle: không xảy ra quá 1 lần/giây cho mỗi contest, kể cả khi có nhiều price events liên tiếp.

3.4 Danh sách participants được cache với TTL 5 giây để tránh query DB liên tục. Sau 5 giây sẽ refresh từ DB.

3.5 Khi client ngắt kết nối (bình thường hoặc đột ngột), client đó được xóa khỏi broadcast set mà không ảnh hưởng đến các clients khác.

---

### Requirement 4: REST endpoint snapshot

**User Story:** Là một user hoặc admin, tôi muốn lấy leaderboard hiện tại qua REST API để tích hợp hoặc debug, không cần mở WebSocket.

#### Acceptance Criteria

4.1 REST endpoint `GET /api/leaderboard/{contest_id}?sort_by=equity` trả về snapshot leaderboard hiện tại.

4.2 Endpoint dùng giá từ `RealtimeMarketCache` nếu có (không phải giá cũ từ DB). Fallback sang Binance REST nếu cache rỗng.

4.3 Khi contest không tồn tại, trả về HTTP 404 với `{"detail": "Contest '{id}' not found"}`.

4.4 Endpoint không yêu cầu authentication (public, giống endpoint leaderboard hiện tại).

4.5 Response bao gồm field `updated_at` (ISO8601 UTC) cho biết thời điểm tính toán.

---

### Requirement 5: Admin xem leaderboard với thông tin chi tiết

**User Story:** Là admin, tôi muốn xem leaderboard với thông tin đầy đủ hơn user thường, bao gồm user_id và participant status, để monitor và moderation.

#### Acceptance Criteria

5.1 Admin có thể kết nối WebSocket tại `/api/leaderboard/ws/{contest_id}?admin_token={jwt}`. Server validate token và gán `is_admin=True`.

5.2 Trong response cho admin, mỗi row có thêm `user_id` (số nguyên) và `participant_status` (`active` | `locked` | `disqualified`).

5.3 Trong response cho user thường (non-admin), `user_id` không xuất hiện trong payload.

5.4 Token invalid hoặc không có quyền admin → server trả `{"type":"error","message":"Unauthorized"}` và đóng connection.

---

### Requirement 6: Xử lý lỗi và trạng thái không ổn định

**User Story:** Là một user, tôi muốn hệ thống hoạt động gracefully khi có sự cố (giá không khả dụng, DB lỗi, client mất kết nối) mà không crash toàn bộ service.

#### Acceptance Criteria

6.1 Khi `RealtimeMarketCache.get_prices()` trả về dict rỗng trong REST request, hệ thống fallback sang Binance REST. Nếu cả hai đều fail → HTTP 503.

6.2 Khi giá không khả dụng trong broadcast loop (cache rỗng), broadcast cycle đó được skip — không gửi snapshot với toàn bộ giá = 0.

6.3 Khi DB query lỗi trong broadcast loop, log error, giữ nguyên participant cache cũ và retry ở cycle tiếp theo. Không crash service.

6.4 Client gửi `sort_by` không hợp lệ (không phải `equity|pnl|roi`) → server trả `{"type":"error","message":"Invalid sort_by"}` nhưng không ngắt connection.

6.5 Khi contest không tồn tại, WS endpoint accept connection, gửi `{"type":"error","message":"Contest not found"}` rồi đóng connection gracefully.

---

### Requirement 7: Frontend cập nhật ContestLeaderboard.vue để dùng WebSocket

**User Story:** Là một user trên giao diện web, tôi muốn trang leaderboard hiển thị dữ liệu cập nhật realtime thay vì chỉ load một lần khi mở trang.

#### Acceptance Criteria

7.1 `ContestLeaderboard.vue` kết nối WebSocket tới `/api/leaderboard/ws/{contest_id}` khi component được mount.

7.2 Khi nhận message `leaderboard_snapshot` hoặc `leaderboard_update`, component cập nhật `rows` reactive data và re-render bảng.

7.3 Component hiển thị indicator trạng thái kết nối: `connecting`, `connected`, `error` (ví dụ badge nhỏ).

7.4 UI cho phép user click vào header column (Equity, PnL, ROI) để đổi sort criterion. Khi click, gửi `{"type":"set_sort","sort_by":"..."}` qua WebSocket.

7.5 Khi component bị unmount (user rời khỏi trang), WebSocket được đóng sạch sẽ.

7.6 Nếu WebSocket không khả dụng hoặc lỗi, component fallback sang REST polling mỗi 10 giây.

---

## Glossary

| Thuật ngữ | Định nghĩa |
|---|---|
| **Equity** | Tổng giá trị tài sản = cash + market value của tất cả positions theo giá realtime |
| **PnL** | Profit and Loss = equity - initial_equity; có thể âm |
| **ROI** | Return on Investment = (pnl / initial_equity) × 100% |
| **Throttle** | Giới hạn tần suất broadcast để tránh quá tải; tối đa 1 lần/giây/contest |
| **Participant Cache** | Danh sách participants được cache trong memory, TTL 5s, để tránh DB query mỗi price tick |
| **RealtimeMarketCache** | In-memory cache giá tài sản, được cập nhật liên tục từ Binance WebSocket feed |
| **Snapshot** | Bản chụp leaderboard tại một thời điểm, gửi ngay khi client kết nối |
| **Leaderboard Update** | Message push xuống clients khi có price update mới (sau khi throttle) |
