import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings

KST = ZoneInfo("Asia/Seoul")

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class KSTFormatter(logging.Formatter):
    """로그 시각을 KST(Asia/Seoul) 기준으로 출력하는 포매터."""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, KST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime(DATE_FORMAT) + f",{int(record.msecs):03d}"


def setup_logging():
    level = logging.INFO
    if settings.ENV.lower() in ["dev", "development", "local"]:
        level = logging.DEBUG

    handler = logging.StreamHandler()
    handler.setFormatter(KSTFormatter(LOG_FORMAT))

    logging.basicConfig(
        level=level,
        handlers=[handler],
        force=True,
    )

    # uvicorn이 자체 핸들러를 붙인 경우에도 KST가 적용되도록 정리
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True