import logging
from abc import ABC, abstractmethod
from typing import Optional
from config import APP_BASE_URL, EMAIL_FROM

logger = logging.getLogger("auth.email_service")


class BaseEmailService(ABC):
    """Abstract base class for email delivery."""

    @abstractmethod
    def send_password_reset_email(self, to_email: str, token: str) -> bool:
        pass

    @abstractmethod
    def send_verification_email(self, to_email: str, token: str) -> bool:
        pass


class ConsoleEmailService(BaseEmailService):
    """
    Development email service that logs email dispatches to console/logger
    without requiring external SMTP or API credentials.
    """

    def __init__(self, from_email: str = EMAIL_FROM, base_url: str = APP_BASE_URL):
        self.from_email = from_email
        self.base_url = base_url.rstrip("/")

    def send_password_reset_email(self, to_email: str, token: str) -> bool:
        reset_link = f"{self.base_url}/auth/reset-password?token={token}"
        logger.info(
            f"[EMAIL SERVICE - DEV] Sending password reset to {to_email}. "
            f"Reset link: {reset_link}"
        )
        # Note: Do not print token directly in production logs; safe dev-level notice
        return True

    def send_verification_email(self, to_email: str, token: str) -> bool:
        verify_link = f"{self.base_url}/auth/verify-email?token={token}"
        logger.info(
            f"[EMAIL SERVICE - DEV] Sending verification email to {to_email}. "
            f"Verification link: {verify_link}"
        )
        return True


# Default email service instance
email_service: BaseEmailService = ConsoleEmailService()


def get_email_service() -> BaseEmailService:
    """Dependency / accessor to retrieve active email service."""
    return email_service

