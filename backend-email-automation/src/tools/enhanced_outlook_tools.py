from .OutlookTools import OutlookTools
from .base_email_tool import BaseEmailTool
from datetime import datetime, timedelta
import os

class EnhancedOutlookTools(OutlookTools):
    def __init__(self, email_address):
        # Check for required environment variables
        required_vars = {
            'OUTLOOK_CLIENT_ID': os.getenv('OUTLOOK_CLIENT_ID'),
            'OUTLOOK_CLIENT_SECRET': os.getenv('OUTLOOK_CLIENT_SECRET'),
            'OUTLOOK_TENANT_ID': os.getenv('OUTLOOK_TENANT_ID')
        }
        
        # Validate all required environment variables are present
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
        client_id = required_vars['OUTLOOK_CLIENT_ID']
        client_secret = required_vars['OUTLOOK_CLIENT_SECRET']
        tenant_id = required_vars['OUTLOOK_TENANT_ID']
        
        super().__init__(client_id, client_secret, tenant_id)
        self.email_address = email_address
        self._initialized = False

    async def ensure_initialized(self):
        """Ensure the client is initialized with valid tokens"""
        if not self._initialized:
            try:
                await self.initialize()
                self._initialized = True
            except Exception as e:
                print(f"Failed to initialize Outlook client: {str(e)}")
                raise

    async def fetch_unanswered_emails(self, max_results=50):
        """Fetch unanswered emails from Outlook"""
        await self.ensure_initialized()
        try:
            # Fetch recent emails
            emails = await self.fetch_emails(top=max_results)
            unanswered_emails = []

            # Get draft emails
            drafts = await self.fetch_draft_replies()
            threads_with_drafts = {draft.get('conversationId') for draft in drafts}

            for email in emails.get('value', []):
                if (email.get('conversationId') not in threads_with_drafts and 
                    not self._should_skip_email(email)):
                    email_info = self._get_email_info(email)
                    unanswered_emails.append(email_info)

            return unanswered_emails
        except Exception as e:
            print(f"Error fetching Outlook emails: {e}")
            return []

    async def fetch_emails(self, folder="inbox", top=10):
        """Fetch recent emails from a specified folder."""
        await self.ensure_initialized()
        try:
            endpoint = f"/me/mailFolders/{folder}/messages?$top={top}&$orderby=receivedDateTime DESC"
            return await self._make_request("GET", endpoint)
        except Exception as e:
            print(f"Error fetching emails: {e}")
            return {"value": []}

    async def create_draft_reply(self, initial_email, reply_text):
        """Create a draft reply in Outlook"""
        await self.ensure_initialized()
        try:
            return await self.draft_email(
                subject=f"Re: {initial_email.subject}",
                body=reply_text,
                to_emails=[initial_email.sender]
            )
        except Exception as e:
            print(f"Error creating Outlook draft: {e}")
            return None

    async def fetch_draft_replies(self):
        """Fetch draft emails from Outlook"""
        await self.ensure_initialized()
        try:
            return (await self._make_request("GET", "/me/mailFolders/drafts/messages")).get('value', [])
        except Exception as e:
            print(f"Error fetching Outlook drafts: {e}")
            return []

    async def send_reply(self, initial_email, reply_text):
        """Send a reply email using Outlook"""
        await self.ensure_initialized()
        try:
            return await self.send_email(
                from_email=self.email_address,
                to_emails=[initial_email.sender],
                subject=f"Re: {initial_email.subject}",
                body=reply_text
            )
        except Exception as e:
            print(f"Error sending Outlook reply: {e}")
            return None