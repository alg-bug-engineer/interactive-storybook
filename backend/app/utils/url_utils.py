"""URL 规范化工具。"""
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def normalize_image_url(image_url: Optional[str]) -> Optional[str]:
    """将历史/本地路径统一为可公开访问的相对路径。"""
    if not image_url:
        return None

    raw = image_url.strip()
    if not raw:
        return None
    if raw.startswith("data:image"):
        return raw

    if raw.startswith("/static/images/"):
        return raw
    if raw.startswith("static/images/"):
        return f"/{raw}"

    # 历史绝对 URL：http://localhost:1001/static/images/xxx.jpg
    if "/static/images/" in raw:
        return raw[raw.index("/static/images/") :]

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        host = parsed.hostname.lower()
        # 非本地且非已知静态路径，保留原值（例如 CDN URL）
        if host not in LOCAL_HOSTS:
            return raw

    normalized = raw.replace("\\", "/")
    if "/data/images/" in normalized or normalized.startswith("data/images/"):
        return f"/static/images/{Path(normalized).name}"
    if "/images/" in normalized and Path(normalized).suffix.lower() in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
    }:
        return f"/static/images/{Path(normalized).name}"

    return raw
