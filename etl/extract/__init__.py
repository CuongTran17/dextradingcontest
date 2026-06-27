"""Extract layer — chỉ fetch dữ liệu, ghi nguyên văn vào ``lake/raw/``.

Mỗi module trong package này:
- Nhận ``EtlConfig`` để biết ngày bắt đầu (đã warm-up) và đường dẫn ghi.
- Không tính indicator, không gộp, không ffill.
- Trả về ``Path`` tới file raw đã ghi (hoặc ``None`` nếu không có dữ liệu).
"""
