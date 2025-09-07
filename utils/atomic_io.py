"""
Atomic I/O Operations (Upgrade #06)
Race-free file operations with atomic writes and file locking
Cross-platform compatible (Windows/Linux/macOS)
"""

import json
import os
import platform
import tempfile
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Platform-specific imports
if platform.system() != "Windows":
    try:
        import fcntl

        HAS_FCNTL = True
    except ImportError:
        HAS_FCNTL = False
else:
    try:
        import msvcrt

        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False
    HAS_FCNTL = False

from config.settings import get_settings
from logging_setup import setup_advanced_logger

logger = setup_advanced_logger("atomic_io")


@dataclass
class LockInfo:
    """Information about file lock"""

    path: str
    process_id: int
    thread_id: int
    timestamp: float
    operation: str


class AtomicFileError(Exception):
    """Base exception for atomic file operations"""

    pass


class FileLockError(AtomicFileError):
    """Exception raised when file locking fails"""

    pass


class AtomicWriteError(AtomicFileError):
    """Exception raised when atomic write fails"""

    pass


# Global lock registry for tracking locks per process/thread
_local_locks = threading.local()


def _get_lock_registry() -> dict[str, LockInfo]:
    """Get thread-local lock registry"""
    if not hasattr(_local_locks, "registry"):
        _local_locks.registry = {}
    return _local_locks.registry


class FileLocker:
    """Cross-platform file locking utility using lock files"""

    def __init__(
        self,
        file_path: str | Path,
        timeout: float = 10.0,
        operation: str = "unknown",
    ):
        self.file_path = str(file_path)
        self.timeout = timeout
        self.operation = operation
        self.lock_file = None

    def __enter__(self):
        """Acquire file lock with timeout using lock file approach"""
        lock_path = f"{self.file_path}.lock"
        registry = _get_lock_registry()

        # Check if already locked in this thread
        if lock_path in registry:
            existing = registry[lock_path]
            logger.warning(
                "Файл энэ тред дээр аль хэдийн түгжээтэй байна",
                extra={
                    "file": self.file_path,
                    "existing_operation": existing.operation,
                    "current_operation": self.operation,
                },
            )
            raise FileLockError(f"File {self.file_path} already locked in thread")

        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Check for stale lock files (older than 2x timeout)
                if os.path.exists(lock_path):
                    try:
                        lock_age = time.time() - os.path.getmtime(lock_path)
                        if lock_age > (self.timeout * 2):
                            logger.warning(
                                "Хуучин түгжээтэй файлыг арилгаж байна",
                                extra={
                                    "file": self.file_path,
                                    "lock_file": lock_path,
                                    "age_seconds": lock_age,
                                },
                            )
                            os.unlink(lock_path)
                    except:
                        pass  # Ignore errors checking/removing stale locks

                # Try to create lock file exclusively
                with open(lock_path, "x", encoding="utf-8") as lock_file:
                    # Write lock info
                    lock_info = LockInfo(
                        path=self.file_path,
                        process_id=os.getpid(),
                        thread_id=threading.get_ident(),
                        timestamp=time.time(),
                        operation=self.operation,
                    )

                    lock_data = {
                        "path": lock_info.path,
                        "pid": lock_info.process_id,
                        "thread_id": lock_info.thread_id,
                        "timestamp": lock_info.timestamp,
                        "operation": lock_info.operation,
                        "iso_time": datetime.fromtimestamp(
                            lock_info.timestamp, tz=UTC
                        ).isoformat(),
                    }

                    json.dump(lock_data, lock_file)
                    lock_file.flush()
                    os.fsync(lock_file.fileno())  # Ensure data is written

                # Register lock
                registry[lock_path] = lock_info
                self.lock_file = lock_path

                logger.debug(
                    "Файлын түгжээ амжилттай авлаа",
                    extra={
                        "file": self.file_path,
                        "operation": self.operation,
                        "lock_file": lock_path,
                    },
                )

                return self

            except FileExistsError:
                # Lock file exists, check if stale
                try:
                    with open(lock_path, encoding="utf-8") as f:
                        lock_data = json.load(f)

                    lock_age = time.time() - lock_data.get("timestamp", 0)

                    # Consider locks older than 5 minutes as stale
                    if lock_age > 300:
                        logger.warning(
                            "Removing stale lock",
                            extra={
                                "file": self.file_path,
                                "lock_age_seconds": lock_age,
                                "stale_operation": lock_data.get(
                                    "operation", "unknown"
                                ),
                            },
                        )

                        try:
                            os.remove(lock_path)
                        except OSError:
                            pass  # Lock might have been removed by another process
                        continue

                except (OSError, json.JSONDecodeError):
                    # Corrupted lock file, try to remove
                    try:
                        os.remove(lock_path)
                    except OSError:
                        pass
                    continue

                # Wait before retrying
                time.sleep(
                    0.05 + (time.time() - start_time) * 0.01
                )  # Progressive backoff

        raise FileLockError(
            f"Could not acquire lock for {self.file_path} within {self.timeout}s"
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release file lock"""
        registry = _get_lock_registry()

        if self.lock_file:
            try:
                os.remove(self.lock_file)

                if self.lock_file in registry:
                    del registry[self.lock_file]

                logger.debug(
                    "Файлын түгжээг суллаа",
                    extra={"file": self.file_path, "operation": self.operation},
                )

            except OSError as e:
                logger.warning(
                    "Түгжээ суллахад алдаа гарлаа",
                    extra={"file": self.file_path, "error": str(e)},
                )


@contextmanager
def file_lock(file_path: str | Path, timeout: float = 10.0, operation: str = "unknown"):
    """Context manager for file locking"""
    locker = FileLocker(file_path, timeout, operation)
    with locker:
        yield


def atomic_write_json(
    file_path: str | Path,
    data: Any,
    indent: int | None = 2,
    ensure_ascii: bool = False,
    create_dirs: bool = True,
    backup: bool = True,
) -> None:
    """
    Atomically write JSON data to file with file locking

    Args:
        file_path: Target file path
        data: Data to write (JSON serializable)
        indent: JSON indentation (None for compact)
        ensure_ascii: Whether to escape non-ASCII characters
        create_dirs: Create parent directories if needed
        backup: Create backup of existing file

    Raises:
        AtomicWriteError: If write operation fails
        FileLockError: If file locking fails
    """
    file_path = Path(file_path)

    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_lock(file_path, operation="atomic_write"):
        try:
            # Create backup if requested and file exists
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
                backup_path.write_bytes(file_path.read_bytes())

            # Create temporary file in the same directory to ensure atomic move
            temp_dir = file_path.parent

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=temp_dir,
                prefix=f".tmp_{file_path.stem}_",
                suffix=".json",
                delete=False,
            ) as temp_file:

                temp_path = Path(temp_file.name)

                # Write JSON data
                json.dump(
                    data,
                    temp_file,
                    ensure_ascii=ensure_ascii,
                    indent=indent,
                    separators=(",", ":") if indent is None else None,
                )
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Force write to disk

            # Atomic move (rename) - this is atomic on most filesystems
            os.replace(temp_path, file_path)

            logger.debug(
                "Атом JSON бичилт амжилттай боллоо",
                extra={"file": str(file_path), "size_bytes": file_path.stat().st_size},
            )

        except Exception as e:
            # Clean up temporary file if it exists
            try:
                if "temp_path" in locals() and temp_path.exists():
                    temp_path.unlink()
            except:
                pass

            logger.error(
                "Атом бичилт амжилтгүй боллоо",
                extra={"file": str(file_path), "error": str(e)},
                exc_info=True,
            )

            raise AtomicWriteError(f"Failed to write {file_path}: {e}") from e


def atomic_read_json(
    file_path: str | Path,
    default: Any = None,
    retry_count: int = 3,
    retry_delay: float = 0.1,
) -> Any:
    """
    Atomically read JSON data from file with file locking

    Args:
        file_path: Source file path
        default: Default value if file doesn't exist or is invalid
        retry_count: Number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Parsed JSON data or default value

    Raises:
        AtomicFileError: If read operation fails after retries
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.debug(
            "Файл олдсонгүй, үндсэн утга буцааж байна",
            extra={"file": str(file_path), "default": default},
        )
        return default

    for attempt in range(retry_count):
        try:
            with file_lock(file_path, operation="atomic_read"):
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                logger.debug(
                    "Атом JSON уншилт амжилттай боллоо",
                    extra={"file": str(file_path), "attempt": attempt + 1},
                )

                return data

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Уншилтын оролдлого амжилтгүй боллоо",
                extra={"file": str(file_path), "attempt": attempt + 1, "error": str(e)},
            )

            if attempt < retry_count - 1:
                time.sleep(retry_delay)
            else:
                logger.error(
                    "Бүх уншилтын оролдлого амжилтгүй",
                    extra={"file": str(file_path), "retry_count": retry_count},
                )
                return default

        except FileLockError as e:
            logger.error(
                "Файлын түгжээ амжилтгүй - уншилтын үед",
                extra={"file": str(file_path), "error": str(e)},
            )
            return default


def atomic_update_json(
    file_path: str | Path,
    update_func: Callable[[Any], Any],
    default: Any = None,
    create_if_missing: bool = True,
) -> Any:
    """
    Atomically update JSON file using a callback function

    Args:
        file_path: Target file path
        update_func: Function that takes current data and returns updated data
        default: Default value for new/missing files
        create_if_missing: Create file if it doesn't exist

    Returns:
        Updated data

    Raises:
        AtomicFileError: If update operation fails
    """
    file_path = Path(file_path)

    with file_lock(file_path, operation="atomic_update"):
        # Read current data without additional locking
        if file_path.exists():
            try:
                with open(file_path, encoding="utf-8") as f:
                    current_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                current_data = default if default is not None else {}
        elif create_if_missing:
            current_data = default if default is not None else {}
        else:
            raise AtomicFileError(
                f"File {file_path} does not exist and create_if_missing=False"
            )

        # Apply update function
        try:
            updated_data = update_func(current_data)
        except Exception as e:
            logger.error(
                "Шинэчлэх функц алдаатай",
                extra={"file": str(file_path), "error": str(e)},
                exc_info=True,
            )
            raise AtomicFileError(f"Update function failed: {e}") from e

        # Write updated data without additional locking (we already hold the lock)
        if file_path.parent and not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Create backup if requested and file exists
            if file_path.exists():
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
                backup_path.write_bytes(file_path.read_bytes())

            # Create temporary file in the same directory
            temp_dir = file_path.parent if file_path.parent else Path(".")

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=temp_dir,
                prefix=f".tmp_{file_path.stem}_",
                suffix=".json",
                delete=False,
            ) as temp_file:

                temp_path = Path(temp_file.name)

                # Write JSON data
                json.dump(updated_data, temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomic move
            os.replace(temp_path, file_path)

        except Exception as e:
            # Clean up temporary file if it exists
            try:
                if "temp_path" in locals() and temp_path.exists():
                    temp_path.unlink()
            except:
                pass

            raise AtomicFileError(f"Failed to write {file_path}: {e}") from e

        logger.info("Атом шинэчлэлт амжилттай хийгдлээ", extra={"file": str(file_path)})

        return updated_data


def cleanup_stale_locks(max_age_seconds: float = 300) -> int:
    """
    Clean up stale lock files older than max_age_seconds

    Args:
        max_age_seconds: Maximum age of lock files in seconds

    Returns:
        Number of stale locks cleaned up
    """
    settings = get_settings()
    cleanup_count = 0

    # Search for .lock files in common directories
    search_paths = [
        Path("."),
        Path("state"),
        Path("logs"),
        settings.logging.log_directory,
    ]

    for search_path in search_paths:
        if not search_path.exists():
            continue

        for lock_file in search_path.glob("*.lock"):
            try:
                # Check file age
                file_age = time.time() - lock_file.stat().st_mtime

                if file_age > max_age_seconds:
                    lock_file.unlink()
                    cleanup_count += 1
                    logger.info(
                        "Хуучин түгжээтэй файлыг устгалаа",
                        extra={"lock_file": str(lock_file), "age_seconds": file_age},
                    )

            except OSError as e:
                logger.warning(
                    "Түгжээтэй файл цэвэрлэхэд алдаа гарлаа",
                    extra={"lock_file": str(lock_file), "error": str(e)},
                )

    if cleanup_count > 0:
        logger.info(
            "Хуучин түгжээ цэвэрлэлт дууслаа", extra={"cleaned_count": cleanup_count}
        )

    return cleanup_count


# Convenience functions for common state files
def read_state_json(filename: str, default: Any = None) -> Any:
    """Read JSON from state directory"""
    return atomic_read_json(Path("state") / filename, default)


def write_state_json(filename: str, data: Any) -> None:
    """Write JSON to state directory"""
    atomic_write_json(Path("state") / filename, data)


def update_state_json(
    filename: str, update_func: Callable[[Any], Any], default: Any = None
) -> Any:
    """Update JSON in state directory"""
    return atomic_update_json(Path("state") / filename, update_func, default)
