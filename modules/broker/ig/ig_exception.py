class ApiExceededException(Exception):
    """Raised when our code hits the IG endpoint too often"""
    pass


class TokenInvalidException(Exception):
    """Raised when the session token is invalid or expired"""
    pass


class IGException(Exception):
    pass


class KycRequiredException(Exception):
    """Raised when IG needs the user to confirm or re-confirm their KYC status"""
    pass
