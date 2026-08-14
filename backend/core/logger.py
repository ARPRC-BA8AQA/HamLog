import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def configure_logging(root, level="INFO"):
    log_dir = Path(root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hamlog")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(logging.StreamHandler())
    return logger
