"""
常驻 Worker：循环执行付款扫描，用户关闭网页后付款也能被确认
阶段 5 再加入退避重试、到期处理和结构化日志
用法（backend 目录）：python -m app.worker，按 Ctrl+C 停止
"""

import logging
import sys
import time

from app.core.config import get_settings
from app.database import SessionLocal
from app.jobs.scan_payments import scan_once

logger = logging.getLogger("app.worker")


def main() -> int:
    # Git Bash 中 Windows 版 Python 默认按 GBK 输出，中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    settings = get_settings()
    logger.info("Worker 启动，每 %d 秒扫描一次", settings.WORKER_POLL_SECONDS)

    try:
        while True:
            try:
                with SessionLocal() as db:
                    summary = scan_once(db)
                if summary.results:
                    logger.info("区块 %d 至 %d 发现付款：%s", summary.from_block, summary.to_block, summary.results)
            except Exception:
                # 单轮失败（如 RPC 或数据库暂时不可用）不退出，下一轮重试；游标未推进，不会漏扫
                logger.exception("本轮扫描失败，%d 秒后重试", settings.WORKER_POLL_SECONDS)
            time.sleep(settings.WORKER_POLL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Worker 已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
