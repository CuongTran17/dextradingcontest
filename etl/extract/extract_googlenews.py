"""Extract tin tức từ Google News cho từng mã cổ phiếu Việt Nam.

Dùng thư viện ``GoogleNews`` để lấy tiêu đề + tóm tắt bài báo.

Raw output:
    lake/raw/google_news/<SYMBOL>/<run_id>.json

Mỗi bản ghi gồm:
    - title       : tiêu đề bài viết
    - desc        : tóm tắt ngắn (snippet)
    - date        : ngày đăng (text relative, ví dụ "2 ngày trước")
    - datetime    : timestamp chuẩn ISO (nếu parse được)
    - link        : URL gốc
    - source      : nguồn báo (VnExpress, CafeF, ...)

Lưu ý:
    - GoogleNews scrape HTML từ Google → cần sleep giữa các symbol
      để tránh bị Google block.
    - Nếu GoogleNews fail → return empty, KHÔNG block pipeline.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from etl.config import EtlConfig
from etl.logging_setup import get_logger

log = get_logger(__name__)

# Rate limit cho Google scraping — tránh bị block
_GOOGLE_NEWS_DELAY_SECONDS: float = 2.0
_MAX_ARTICLES_PER_QUERY: int = 10
_GOOGLE_NEWS_MOJIBAKE_MARKERS = ("├", "┬", "ß", "╗", "║", "─", "Ī", "Ę", "Ł", "ć", "ō", "░", "┐")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or not any(marker in text for marker in _GOOGLE_NEWS_MOJIBAKE_MARKERS):
        return text

    try:
        repaired = text.encode("cp775").decode("utf-8")
    except UnicodeError:
        return text

    original_marker_count = sum(text.count(marker) for marker in _GOOGLE_NEWS_MOJIBAKE_MARKERS)
    repaired_marker_count = sum(repaired.count(marker) for marker in _GOOGLE_NEWS_MOJIBAKE_MARKERS)
    return repaired if repaired_marker_count < original_marker_count else text


def _parse_relative_date(date_str: str) -> Optional[str]:
    """Cố parse date string relative (ví dụ '2 ngày trước') thành ISO date.

    Trả về None nếu không parse được — GoogleNews có thể trả format bất kỳ.
    """
    try:
        # GoogleNews cung cấp datetime object thông qua results()
        # nhưng không phải lúc nào cũng có — đây chỉ là fallback
        from dateparser import parse as dateparse
        parsed = dateparse(date_str, languages=["vi", "en"])
        if parsed:
            return parsed.strftime("%Y-%m-%d")
    except ImportError:
        pass
    except Exception:
        pass
    return None


def _fetch_google_news(symbol: str, period: str = "7d") -> list[dict[str, Any]]:
    """Gọi GoogleNews để lấy tin tức cho 1 mã cổ phiếu.

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu (FPT, MBB, ...)
    period : str
        Khoảng thời gian (7d, 30d, ...)

    Returns
    -------
    list[dict] — danh sách tin tức (tối đa _MAX_ARTICLES_PER_QUERY)
    """
    try:
        from GoogleNews import GoogleNews
    except ImportError:
        log.error("GoogleNews library not installed. Run: pip install GoogleNews")
        return []

    articles: list[dict[str, Any]] = []

    # Tìm kiếm tin tức: thử các query theo thứ tự:
    # 1. Các query với keywords cụ thể (mặc dù không luôn trả kết quả tốt)
    # 2. Query đơn giản như fallback
    # Google News API không hỗ trợ tốt "AND" / "+" trong tiếng Việt,
    # nên ta dùng space-separated keywords hoặc fallback đến symbol đơn.
    queries = [
        f"{symbol} chứng khoán",     # Try specific first (may return 0-1 result)
        f"{symbol} cổ phiếu",        # Alternative specific
        symbol,                       # Fallback: broad search for symbol
    ]

    try:
        gn = GoogleNews(lang="vi", region="VN", period=period)
        gn.enableException(True)

        seen_titles: set[str] = set()

        for query in queries:
            if len(articles) >= _MAX_ARTICLES_PER_QUERY:
                break

            try:
                gn.clear()
                gn.search(query)
                results = gn.results(sort=True)

                for item in results:
                    # Skip None items (API sometimes returns malformed results)
                    if item is None:
                        continue
                    
                    title = _safe_str(item.get("title"))
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    date_raw = _safe_str(item.get("date"))
                    dt_obj = item.get("datetime")  # GoogleNews có thể trả datetime object

                    article = {
                        "title": title,
                        "desc": _safe_str(item.get("desc")),
                        "date": date_raw,
                        "datetime": dt_obj.isoformat() if isinstance(dt_obj, datetime) else _parse_relative_date(date_raw),
                        "link": _safe_str(item.get("link")),
                        "source": _safe_str(item.get("media")),
                        "symbol": symbol,
                    }
                    articles.append(article)

                    if len(articles) >= _MAX_ARTICLES_PER_QUERY:
                        break

            except Exception as exc:
                log.info("GoogleNews query '%s' failed for %s: %s", query, symbol, exc)
                # Continue to next query if this one fails
                continue

    except Exception as exc:
        log.warning("GoogleNews init/search failed for %s: %s", symbol, exc)
        return []

    return articles


def extract_google_news(symbol: str, cfg: EtlConfig) -> Optional[Path]:
    """Extract tin tức Google News cho 1 mã cổ phiếu, ghi raw JSON.

    Trả về đường dẫn file đã ghi hoặc None.
    """
    try:
        articles = _fetch_google_news(symbol, period=cfg.google_news_period)
    except Exception as exc:
        log.warning("GoogleNews extract failed for %s: %s", symbol, exc)
        articles = []

    # Ghi ra file JSON kể cả khi empty (để transform layer biết đã chạy)
    out = cfg.raw_path("google_news", symbol=symbol, suffix="json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(articles, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    log.info(
        "Saved google_news %s -> %s (%d articles)",
        symbol, out, len(articles),
    )

    # Sleep giữa các symbol để tránh Google block
    time.sleep(_GOOGLE_NEWS_DELAY_SECONDS)
    return out


# ---------------------------------------------------------------------------
# Loader — đọc lại raw cho transform layer
# ---------------------------------------------------------------------------
def load_google_news(symbol: str, cfg: EtlConfig) -> list[dict[str, Any]]:
    """Đọc lại raw JSON Google News đã ghi ở lần chạy hiện tại."""
    path = cfg.raw_dir / "google_news" / symbol.upper() / f"{cfg.run_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, Exception) as exc:
        log.exception("Corrupt google_news JSON: %s — %s", path, exc)
        return []
