from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone


@dataclass(frozen=True)
class StoredDownload:
    name: str
    size: int


@dataclass(frozen=True)
class DownloadEntry:
    name: str
    relative_path: str
    size: int
    modified: datetime


class DownloadUploadError(ValueError):
    pass


def download_library_dir() -> Path:
    return Path(settings.DOWNLOAD_LIBRARY_DIR)


def prepare_download_library() -> Path:
    library = download_library_dir()
    library.mkdir(parents=True, exist_ok=True)
    (library / ".upload-tmp").mkdir(mode=0o700, exist_ok=True)
    return library


def safe_download_name(filename: str) -> str:
    name = str(filename or "").strip()
    if (
        not name
        or name in {".", ".."}
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or any(ord(character) < 32 for character in name)
        or len(name.encode("utf-8")) > 240
    ):
        raise DownloadUploadError("The filename is not supported.")
    return name


def next_available_path(library: Path, filename: str) -> Path:
    candidate = library / filename
    if not candidate.exists():
        return candidate

    original = Path(filename)
    number = 2
    while True:
        candidate = library / f"{original.stem} ({number}){original.suffix}"
        if not candidate.exists():
            return candidate
        number += 1


def store_uploaded_files(
    uploaded_files: list[UploadedFile],
    *,
    conflict_policy: str,
) -> tuple[StoredDownload, ...]:
    if conflict_policy not in {"rename", "replace"}:
        raise DownloadUploadError("Choose Replace existing or Keep both.")
    if not uploaded_files:
        raise DownloadUploadError("Choose at least one file.")
    if len(uploaded_files) > settings.DOWNLOAD_UPLOAD_MAX_FILES:
        raise DownloadUploadError(
            f"Upload no more than {settings.DOWNLOAD_UPLOAD_MAX_FILES} files at once."
        )

    validated_uploads: list[tuple[UploadedFile, str]] = []
    for uploaded in uploaded_files:
        name = safe_download_name(uploaded.name)
        if uploaded.size > settings.DOWNLOAD_UPLOAD_MAX_BYTES:
            max_mib = settings.DOWNLOAD_UPLOAD_MAX_BYTES // (1024 * 1024)
            raise DownloadUploadError(f"{name} is larger than {max_mib} MiB.")
        validated_uploads.append((uploaded, name))

    library = prepare_download_library()
    staging_directory = library / ".upload-tmp"
    stored: list[StoredDownload] = []
    for uploaded, name in validated_uploads:
        temporary_path: Path | None = None
        try:
            uploaded_temporary_path = getattr(
                uploaded,
                "temporary_file_path",
                None,
            )
            if os.name == "posix" and callable(uploaded_temporary_path):
                candidate = Path(uploaded_temporary_path())
                if (
                    candidate.is_file()
                    and candidate.resolve().parent == staging_directory.resolve()
                ):
                    # Django has already streamed a large upload into our
                    # staging directory. Flush and promote that same file
                    # instead of copying another multi-gigabyte temporary file.
                    uploaded.file.flush()
                    os.fsync(uploaded.file.fileno())
                    temporary_path = candidate
                    bytes_written = uploaded.size

            if temporary_path is None:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=".nvgs-web-upload-",
                    suffix=".part",
                    dir=staging_directory,
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    bytes_written = 0
                    for chunk in uploaded.chunks():
                        bytes_written += len(chunk)
                        if bytes_written > settings.DOWNLOAD_UPLOAD_MAX_BYTES:
                            max_mib = (
                                settings.DOWNLOAD_UPLOAD_MAX_BYTES // (1024 * 1024)
                            )
                            raise DownloadUploadError(
                                f"{name} is larger than {max_mib} MiB."
                            )
                        temporary_file.write(chunk)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())

            temporary_path.chmod(0o644)
            if conflict_policy == "replace":
                destination = library / name
                os.replace(temporary_path, destination)
            else:
                while True:
                    destination = next_available_path(library, name)
                    try:
                        os.link(temporary_path, destination)
                        break
                    except FileExistsError:
                        continue
                temporary_path.unlink()
            temporary_path = None
            stored.append(StoredDownload(destination.name, bytes_written))
        except OSError as exc:
            raise DownloadUploadError(f"Could not store {name}: {exc}") from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return tuple(stored)


def list_download_entries() -> tuple[DownloadEntry, ...]:
    library = prepare_download_library()
    entries: list[DownloadEntry] = []
    for item in library.rglob("*"):
        relative = item.relative_to(library)
        if any(part.startswith(".") for part in relative.parts) or item.is_symlink():
            continue
        try:
            if not item.is_file():
                continue
            stat = item.stat()
        except OSError:
            continue
        entries.append(
            DownloadEntry(
                name=item.name,
                relative_path=relative.as_posix(),
                size=stat.st_size,
                modified=datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.get_current_timezone(),
                ),
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.relative_path.lower()))
