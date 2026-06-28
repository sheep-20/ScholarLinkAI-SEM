"""
重试工具 - 用于处理API配额限制等临时错误
"""
from __future__ import annotations

import time
import logging
from typing import Callable, TypeVar, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_quota_error(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0
):
    """
    装饰器：在遇到配额错误时自动重试
    
    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子（每次重试延迟乘以这个值）
        max_delay: 最大延迟（秒）
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RuntimeError as e:
                    error_msg = str(e)
                    # 检查是否是配额错误
                    is_quota_error = (
                        "quota" in error_msg.lower() or
                        "429" in error_msg or
                        "rate limit" in error_msg.lower() or
                        "TooManyRequests" in error_msg
                    )
                    
                    if is_quota_error and attempt < max_retries:
                        last_exception = e
                        logger.warning(
                            f"{func.__name__} 遇到配额限制（尝试 {attempt + 1}/{max_retries + 1}），"
                            f"等待 {delay:.1f} 秒后重试..."
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                        continue
                    else:
                        # 不是配额错误，或者重试次数用完，直接抛出
                        raise
                except Exception as e:
                    # 其他错误直接抛出，不重试
                    raise
            
            # 所有重试都失败
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} 重试 {max_retries} 次后仍然失败")
        
        return wrapper
    return decorator


__all__ = ["retry_on_quota_error"]


