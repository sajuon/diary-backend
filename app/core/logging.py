import logging
from app.core.config import settings


def setup_logging():
    level = logging.INFO
    if settings.ENV.lower() in ["dev", "development", "local"]:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
