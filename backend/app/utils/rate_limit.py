"""Single application-wide SlowAPI limiter."""

from pathlib import Path

from slowapi import Limiter

from app.utils.ip_utils import get_client_ip


_CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "rate_limit.env"
limiter = Limiter(key_func=get_client_ip, config_filename=str(_CONFIG_FILE))
