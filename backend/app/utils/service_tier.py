"""服务等级判断工具"""
from typing import Literal, Optional


def get_service_tier(user: Optional[dict]) -> Literal["free", "premium"]:
    """
    根据用户信息返回服务等级

    Args:
        user: 用户信息字典，包含 is_paid 字段
              - None: 未登录用户 → free
              - is_paid=False: 免费用户 → free
              - is_paid=True: 付费用户 → premium

    Returns:
        "free": 使用本地服务（jimeng-api + edge-tts）
        "premium": 使用官方 API（火山即梦 + 火山 TTS）

    Examples:
        >>> get_service_tier(None)
        'free'
        >>> get_service_tier({"email": "user@example.com", "is_paid": False})
        'free'
        >>> get_service_tier({"email": "premium@example.com", "is_paid": True})
        'premium'
    """
    if not user or not user.get("is_paid"):
        return "free"
    return "premium"


def get_user_identifier(user: Optional[dict]) -> str:
    """
    获取用户标识，用于日志记录

    Args:
        user: 用户信息字典

    Returns:
        用户邮箱 或 "未登录"

    Examples:
        >>> get_user_identifier(None)
        '未登录'
        >>> get_user_identifier({"email": "user@example.com"})
        'user@example.com'
    """
    if not user:
        return "未登录"
    return user.get("email", "未知用户")


def is_premium_user(user: Optional[dict]) -> bool:
    """
    判断是否为付费用户

    Args:
        user: 用户信息字典

    Returns:
        True: 付费用户
        False: 免费用户或未登录用户

    Examples:
        >>> is_premium_user(None)
        False
        >>> is_premium_user({"is_paid": False})
        False
        >>> is_premium_user({"is_paid": True})
        True
    """
    return bool(user and user.get("is_paid"))
