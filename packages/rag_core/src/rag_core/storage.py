"""Generated storage keys, bounded streaming, and integrity hashes."""

import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

from rag_core.errors import PlatformError
from rag_core.extraction import FORMATS


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root) or target == self.root:
            raise PlatformError("invalid_storage_key", "Invalid artifact location.")
        return target

    async def upload(
        self, filename: str, read: Callable[[int], Awaitable[bytes]], limit: int
    ) -> tuple[str, str, int, str]:
        suffix = Path(filename).suffix.lower()
        if suffix not in FORMATS:
            raise PlatformError("unsupported_format", "Use PDF, HTML, Markdown, or UTF-8 text.")
        key = f"originals/{uuid4().hex}{suffix}"
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        try:
            with target.open("xb") as stream:
                while chunk := await read(1_048_576):
                    size += len(chunk)
                    if size > limit:
                        raise PlatformError(
                            "upload_too_large", "The file exceeds the upload limit.", 413
                        )
                    digest.update(chunk)
                    stream.write(chunk)
            if not size:
                raise PlatformError("empty_document", "The uploaded file is empty.")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        mime = {
            "pdf": "application/pdf",
            "html": "text/html",
            "markdown": "text/markdown",
            "text": "text/plain",
        }[FORMATS[suffix]]
        return key, digest.hexdigest(), size, mime
