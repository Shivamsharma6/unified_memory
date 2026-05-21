class UAMSError(Exception):
    """Base exception for UAMS SDK."""
    pass

class UAMSConnectionError(UAMSError):
    """Raised when the API is unreachable."""
    pass

class UAMSAPIError(UAMSError):
    """Raised when the API returns an error response."""
    def __init__(self, message: str, status_code: int = None, details: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details
