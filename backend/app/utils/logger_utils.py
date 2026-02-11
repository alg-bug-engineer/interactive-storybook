"""统一日志格式工具"""
import time
from typing import Optional, Literal, Callable
from functools import wraps
import logging


def log_service_call(
    logger: logging.Logger,
    service_type: Literal["图片生成", "TTS生成", "视频生成"],
    tier: Literal["free", "premium"],
    user_email: str,
    **kwargs
) -> None:
    """
    记录服务调用日志

    Args:
        logger: 日志记录器
        service_type: 服务类型
        tier: 服务等级
        user_email: 用户邮箱或"未登录"
        **kwargs: 额外的日志信息（如 prompt, voice_id 等）

    Examples:
        >>> log_service_call(
        ...     logger,
        ...     service_type="图片生成",
        ...     tier="premium",
        ...     user_email="user@example.com",
        ...     style_id="q_cute"
        ... )
    """
    service_name = "官方API" if tier == "premium" else "本地服务"
    extra_info = ", ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    extra_str = f", {extra_info}" if extra_info else ""

    logger.info(
        f"[{service_type}] 服务类型: {service_name}, 用户: {user_email}{extra_str}"
    )


def log_cache_check(
    logger: logging.Logger,
    service_type: Literal["图片", "音频"],
    cache_hit: bool,
    cache_key: str,
) -> None:
    """
    记录缓存检查日志

    Args:
        logger: 日志记录器
        service_type: 服务类型
        cache_hit: 是否命中缓存
        cache_key: 缓存键

    Examples:
        >>> log_cache_check(logger, "图片", True, "abc123")
        [图片缓存] 检查: ✅ 命中, 缓存键: abc123
    """
    status = "✅ 命中" if cache_hit else "❌ 未命中"
    logger.info(f"[{service_type}缓存] 检查: {status}, 缓存键: {cache_key[:16]}...")


def log_generation_result(
    logger: logging.Logger,
    service_type: Literal["图片生成", "TTS生成", "视频生成"],
    success: bool,
    elapsed: float,
    output_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    记录生成结果日志

    Args:
        logger: 日志记录器
        service_type: 服务类型
        success: 是否成功
        elapsed: 耗时（秒）
        output_path: 输出路径
        error: 错误信息

    Examples:
        >>> log_generation_result(
        ...     logger,
        ...     "图片生成",
        ...     True,
        ...     2.5,
        ...     "data/images/abc123.jpg"
        ... )
        [图片生成] ✅ 生成完成，耗时: 2.50s, 路径: data/images/abc123.jpg
    """
    if success:
        path_str = f", 路径: {output_path}" if output_path else ""
        logger.info(
            f"[{service_type}] ✅ 生成完成，耗时: {elapsed:.2f}s{path_str}"
        )
    else:
        error_str = f", 错误: {error}" if error else ""
        logger.error(
            f"[{service_type}] ❌ 生成失败，耗时: {elapsed:.2f}s{error_str}"
        )


def timed_execution(service_type: str):
    """
    装饰器：自动记录函数执行时间

    Args:
        service_type: 服务类型名称

    Examples:
        @timed_execution("图片生成")
        async def generate_image(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            logger = logging.getLogger(func.__module__)

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"[{service_type}] ⏱️ 执行耗时: {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"[{service_type}] ❌ 执行失败，耗时: {elapsed:.2f}s, 错误: {e}",
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        格式化的文件大小字符串

    Examples:
        >>> format_file_size(1024)
        '1.0 KB'
        >>> format_file_size(1536000)
        '1.5 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
