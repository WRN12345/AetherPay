"""
常驻 Worker：循环执行付款扫描和到期处理，用户关闭网页后付款也能被确认
用法（backend 目录）：python -m app.worker，按 Ctrl+C 停止
"""

import logging
import sys
import time

from app.core.config import get_settings
from app.database import SessionLocal
from app.jobs.expire_orders import expire_orders
from app.jobs.scan_payments import scan_once
from app.services.chain import get_web3

logger = logging.getLogger("app.worker")


def backoff_delay(failures: int, base: int, maximum: int) -> int:
    """连续失败时的等待秒数：base、2×base、4×base…，不超过 maximum"""
    if failures <= 0:
        return base
    return min(base * 2 ** (failures - 1), maximum)


def run_round() -> None:
    """执行一轮：扫描付款，再处理到期；任何异常都向上抛出，由主循环决定重试"""
    with SessionLocal() as db:
        scan_once(db)
        expire_orders(db, get_web3().eth.block_number)


def main() -> int:
    # Git Bash 中 Windows 版 Python 默认按 GBK 输出，中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    settings = get_settings()
    logger.info(
        "worker_start poll_seconds=%d max_backoff_seconds=%d",
        settings.WORKER_POLL_SECONDS,
        settings.WORKER_MAX_BACKOFF_SECONDS,
    )

    failures = 0
    try:
        while True:
            try:
                run_round()
                if failures:
                    logger.info("worker_recovered after_failures=%d", failures)
                failures = 0
            except Exception as exc:
                # RPC 或数据库暂时不可用时不退出；本轮事务已回滚、游标未推进，恢复后从原位置继续，不会漏扫
                failures += 1
                if failures == 1:
                    logger.exception("worker_round_failed failures=1")
                else:
                    # 连续失败只打印一行，避免刷屏
                    logger.error("worker_round_failed failures=%d error=%s: %s", failures, type(exc).__name__, exc)
            delay = backoff_delay(failures, settings.WORKER_POLL_SECONDS, settings.WORKER_MAX_BACKOFF_SECONDS)
            if failures:
                logger.warning("worker_retry_in seconds=%d", delay)
            time.sleep(delay)
    except KeyboardInterrupt:
        logger.info("worker_stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
