"""Safe domain errors shared by HTTP endpoints and ingestion jobs."""


class PlatformError(Exception):
    def __init__(
        self, code: str, message: str, status: int = 422, *, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


class LostLease(Exception):
    """An expired/reassigned worker must not publish any more state."""
