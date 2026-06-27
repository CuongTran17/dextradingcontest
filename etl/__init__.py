"""ETL pipeline for Vietnamese market data.

Kiến trúc Medallion:
- lake/raw/        : response gốc từ vnstock / HTTP API, không biến đổi.
- lake/processed/  : dataset sạch (đã tính indicator, ffill macro, cắt warm-up).

Module con:
- config            : cấu hình tập trung (start/end date, warmup, concurrency, paths).
- logging_setup     : logging rotating file + console.
- retry             : decorator tenacity dùng chung cho tất cả lời gọi API.
- extract/          : chỉ fetch và ghi raw (không biến đổi).
- transform/        : chỉ đọc raw, tính indicator, ghép dataset sạch.
- run_etl           : orchestrator chạy Extract → Transform.
"""

__all__ = ["config", "logging_setup", "retry", "extract", "transform", "run_etl"]
