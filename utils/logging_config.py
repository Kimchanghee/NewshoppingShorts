"""
Centralized Logging Configuration

This module provides structured logging with file rotation and colored console output.
Replaces all print() statements across the codebase with proper logging levels.

Usage:
    from utils.logging_config import AppLogger

    # Setup logging at application startup
    AppLogger.setup(log_dir=Path("logs"), level="INFO")

    # Get module-specific logger
    logger = AppLogger.get_logger(__name__)
    logger.info("Application started")
    logger.error("Error occurred", exc_info=True)
"""

import logging
import logging.handlers
import sys
import io
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import traceback

try:
    from colorama import Fore, Style, init as colorama_init
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    Fore = None
    Style = None


def _configure_windows_console_utf8() -> None:
    """
    Windows 콘솔에서 UTF-8 출력을 위한 설정
    Configure Windows console for proper UTF-8 output
    """
    if sys.platform != "win32":
        return

    try:
        # Windows 콘솔 코드 페이지를 UTF-8 (65001)로 설정
        # Set Windows console code page to UTF-8 (65001)
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # SetConsoleOutputCP(65001) - UTF-8
        kernel32.SetConsoleOutputCP(65001)
        # SetConsoleCP(65001) - UTF-8 for input
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    try:
        # stdout/stderr를 UTF-8로 재설정
        # Reconfigure stdout/stderr to UTF-8
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )

        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except Exception:
        pass

    # 환경 변수 설정으로 Python 전체에 UTF-8 강제
    # Force UTF-8 encoding via environment variables
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""

    # Color mapping for log levels
    COLORS = {
        'DEBUG': Fore.CYAN if COLORAMA_AVAILABLE else '',
        'INFO': Fore.GREEN if COLORAMA_AVAILABLE else '',
        'WARNING': Fore.YELLOW if COLORAMA_AVAILABLE else '',
        'ERROR': Fore.RED if COLORAMA_AVAILABLE else '',
        'CRITICAL': Fore.RED + Style.BRIGHT if COLORAMA_AVAILABLE else '',
    }

    RESET = Style.RESET_ALL if COLORAMA_AVAILABLE else ''

    def __init__(self, fmt: str = None, datefmt: str = None):
        """
        Initialize colored formatter.

        Args:
            fmt: Log format string
            datefmt: Date format string
        """
        if fmt is None:
            fmt = '[%(levelname)s] %(name)s - %(message)s'
        if datefmt is None:
            datefmt = '%Y-%m-%d %H:%M:%S'
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted and colored log string
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        result = super().format(record)

        # Restore original level name
        record.levelname = levelname

        return result


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging of errors"""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        import json

        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_data, ensure_ascii=False)


class AppLogger:
    """
    Centralized application logger with console and file handlers.

    This class provides a singleton-like interface for setting up logging
    across the entire application.
    """

    _initialized = False
    _loggers = {}

    @classmethod
    def setup(
        cls,
        log_dir: Path,
        level: str = "INFO",
        console_level: Optional[str] = None,
        file_level: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_json: bool = True
    ) -> logging.Logger:
        """
        Setup application-wide logging configuration.

        This should be called once at application startup.

        Args:
            log_dir: Directory to store log files
            level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_level: Console-specific log level (overrides level)
            file_level: File-specific log level (overrides level)
            max_bytes: Maximum size of each log file before rotation
            backup_count: Number of backup log files to keep
            enable_json: Enable JSON-formatted error logs

        Returns:
            Root logger instance

        Example:
            >>> AppLogger.setup(Path("logs"), level="DEBUG")
            >>> logger = AppLogger.get_logger(__name__)
            >>> logger.info("Application started")
        """
        if cls._initialized:
            return logging.getLogger()

        # Windows 콘솔 UTF-8 설정 (colorama 초기화 전에 수행)
        # Configure Windows console for UTF-8 (before colorama init)
        _configure_windows_console_utf8()

        # Initialize colorama for Windows
        if COLORAMA_AVAILABLE:
            colorama_init(autoreset=True)

        # Create log directory
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all, filter in handlers

        # Remove existing handlers
        root_logger.handlers.clear()

        # Determine log levels
        console_level = console_level or level
        file_level = file_level or level

        # === Console Handler (colored) ===
        # UTF-8 스트림 생성 (Windows 호환성 보장)
        # Create UTF-8 stream for Windows compatibility
        try:
            if hasattr(sys.stdout, "buffer"):
                utf8_stream = io.TextIOWrapper(
                    sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
                )
            else:
                utf8_stream = sys.stdout
        except Exception:
            utf8_stream = sys.stdout

        console_handler = logging.StreamHandler(utf8_stream)
        console_handler.setLevel(getattr(logging, console_level.upper()))

        console_formatter = ColoredFormatter(
            fmt='[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # === File Handler (rotating) ===
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, file_level.upper()))

        file_formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # === JSON Error Handler (for ERROR and above) ===
        if enable_json:
            json_log_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.json"
            json_handler = logging.handlers.RotatingFileHandler(
                json_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            json_handler.setLevel(logging.ERROR)
            json_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(json_handler)

        cls._initialized = True

        # Log initialization
        init_logger = cls.get_logger("logging_config")
        init_logger.info(f"Logging initialized - Level: {level}, Log dir: {log_dir}")

        return root_logger

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a module-specific logger.

        Args:
            name: Logger name (typically __name__ of the calling module)

        Returns:
            Logger instance for the specified module

        Example:
            >>> logger = AppLogger.get_logger(__name__)
            >>> logger.debug("Debugging message")
            >>> logger.info("Informational message")
            >>> logger.warning("Warning message")
            >>> logger.error("Error message", exc_info=True)
        """
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]

    @classmethod
    def set_level(cls, name: str, level: str):
        """
        Set log level for a specific logger.

        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Example:
            >>> AppLogger.set_level("processors.subtitle_detector", "DEBUG")
        """
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper()))

    @classmethod
    def disable_logger(cls, name: str):
        """
        Disable a specific logger.

        Args:
            name: Logger name to disable

        Example:
            >>> AppLogger.disable_logger("noisy_module")
        """
        logger = logging.getLogger(name)
        logger.disabled = True

    @classmethod
    def enable_logger(cls, name: str):
        """
        Enable a previously disabled logger.

        Args:
            name: Logger name to enable

        Example:
            >>> AppLogger.enable_logger("noisy_module")
        """
        logger = logging.getLogger(name)
        logger.disabled = False


# Convenience function for quick logger access
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance (convenience wrapper).

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        >>> from utils.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Message")
    """
    return AppLogger.get_logger(name)


# Backward compatibility: Safe print function that uses logging
def safe_print(msg: str, level: str = "INFO"):
    """
    Backward compatibility function for migrating from print() to logging.

    This function can be used as a drop-in replacement for print() statements
    during the migration process.

    Args:
        msg: Message to log
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Example:
        >>> safe_print("[OCR] Initializing OCR engine")
        >>> safe_print("[ERROR] Failed to load model", level="ERROR")

    Deprecated: Use logger.info() instead
    """
    logger = get_logger("legacy")
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(msg)
