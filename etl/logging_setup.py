"""Cấu hình logging dùng chung cho toàn bộ pipeline.

- Console handler: hiện INFO trở lên (dễ đọc khi chạy tay).
- File handler: RotatingFileHandler ghi đầy đủ DEBUG vào ``logs/etl.log``
  (giữ 5 file x 10 MB).

Thay thế hoàn toàn cho ``print()`` rải rác trong codebase cũ.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(log_dir: str | Path = "logs", level: int = logging.INFO) -> logging.Logger:
    """Khởi tạo logging root. Idempotent – gọi nhiều lần vẫn an toàn."""
    global _CONFIGURED

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if _CONFIGURED:
        return root

    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-35s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    fh = RotatingFileHandler(
        log_dir / "etl.log",
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Thư viện third-party hay spam DEBUG -> nâng lên WARNING.
    for noisy in ("urllib3", "requests", "charset_normalizer", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Alias ngắn gọn để các module dùng ``get_logger(__name__)``."""
    return logging.getLogger(name)
