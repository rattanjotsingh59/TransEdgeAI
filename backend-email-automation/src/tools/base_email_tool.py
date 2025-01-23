from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class BaseEmailTool(ABC):
    """
    Abstract base class defining the interface for email service implementations.
    All email service classes (Gmail, Outlook, etc.) should implement this interface.
    """

    @abstractmethod
    async def fetch_unanswered_emails(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch unanswered emails from the email service.

        Args:
            max_results (int): Maximum number of emails to fetch

        Returns:
            List[Dict[str, Any]]: List of email dictionaries containing:
                - id (str): Email ID
                - threadId (str): Thread ID
                - messageId (str): Message ID
                - references (str): Email references
                - sender (str): Sender email address
                - subject (str): Email subject
                - body (str): Email body content
                - isUnread (bool): Whether the email is unread
                - labels (List[str]): Email labels/categories
        """
        pass

    @abstractmethod
    async def create_draft_reply(self, initial_email: Dict[str, Any], reply_text: str) -> Optional[Dict[str, Any]]:
        """
        Create a draft reply to an email.

        Args:
            initial_email (Dict[str, Any]): Original email to reply to
            reply_text (str): Content of the reply

        Returns:
            Optional[Dict[str, Any]]: Draft email information if successful, None if failed
        """
        pass

    @abstractmethod
    async def send_reply(self, initial_email: Dict[str, Any], reply_text: str) -> Optional[Dict[str, Any]]:
        """
        Send a reply to an email.

        Args:
            initial_email (Dict[str, Any]): Original email to reply to
            reply_text (str): Content of the reply

        Returns:
            Optional[Dict[str, Any]]: Sent email information if successful, None if failed
        """
        pass

    @abstractmethod
    async def fetch_draft_replies(self) -> List[Dict[str, Any]]:
        """
        Fetch all draft replies from the email service.

        Returns:
            List[Dict[str, Any]]: List of draft email dictionaries containing:
                - draft_id (str): Draft ID
                - threadId (str): Thread ID
                - id (str): Message ID
        """
        pass

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass

    async def cleanup(self):
        """
        Cleanup resources used by the email tool.
        Should be implemented by classes that need resource cleanup.
        """
        pass