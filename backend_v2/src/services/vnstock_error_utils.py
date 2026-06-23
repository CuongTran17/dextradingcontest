import re


def is_rate_limit_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "rate limit exceeded" in message
        or "gioi han api" in message
        or "giới hạn api" in message
        or "you have reached the maximum api request limit" in message
    )


def extract_retry_after_seconds(exc: BaseException, default_seconds: float = 20.0) -> float:
    message = str(exc).lower()

    patterns = [
        r"ch[oờ]\s*(\d+)\s*gi[âa]y",
        r"wait\s*(\d+)\s*seconds?",
        r"retry\s*after\s*(\d+)\s*s",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            try:
                return max(float(match.group(1)), 1.0)
            except (TypeError, ValueError):
                continue

    return max(default_seconds, 1.0)
