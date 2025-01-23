import ssl
import certifi
import aiohttp
from msal import ConfidentialClientApplication
from .base_email_tool import BaseEmailTool
import asyncio

class OutlookTools(BaseEmailTool):
    def __init__(self, client_id, client_secret, tenant_id):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.session = None
        self.token = None
        self.app = None
        self.email_address = None
        self.scopes = ['https://graph.microsoft.com/.default']
        
    def _create_msal_app(self):
        """Create MSAL confidential client application"""
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        return ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=authority
        )

    async def initialize(self):
        """Initialize the client credentials flow and get access token"""
        try:
            # Create MSAL app if not already created
            if not self.app:
                self.app = self._create_msal_app()
            
            # Try to get token silently first
            result = self.app.acquire_token_silent(
                scopes=self.scopes,
                account=None
            )
            
            # If no token in cache, get new one
            if not result:
                result = self.app.acquire_token_for_client(scopes=self.scopes)
            
            if 'access_token' in result:
                self.token = result['access_token']
            else:
                error_msg = result.get('error_description', 'Unknown error')
                raise Exception(f"Could not obtain access token: {error_msg}")
                
        except Exception as e:
            raise

    async def _get_session(self):
        """Get or create aiohttp session with SSL context"""
        if self.session is None or self.session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session

    async def _make_request(self, method, endpoint, payload=None):
        """Make async request to Microsoft Graph API with token refresh"""
        if not self.token:
            await self.initialize()

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        
        try:
            async with session.request(method, url, headers=headers, json=payload, ssl=False) as response:
                if response.status == 401:  # Token expired
                    await self.initialize()  # Get new token
                    headers["Authorization"] = f"Bearer {self.token}"
                    async with session.request(method, url, headers=headers, json=payload, ssl=False) as retry_response:
                        if retry_response.status in [200, 201]:
                            return await retry_response.json()
                        else:
                            text = await retry_response.text()
                            raise Exception(f"Error after token refresh: {retry_response.status}, {text}")
                elif response.status in [200, 201]:
                    return await response.json()
                else:
                    text = await response.text()
                    raise Exception(f"Error: {response.status}, {text}")
        except Exception as e:
            raise

    async def fetch_unanswered_emails(self, max_results=50):
        """Fetch unanswered emails from Outlook"""
        try:
            endpoint = f"/users/{self.email_address}/messages?$top={max_results}&$orderby=receivedDateTime desc"
            emails = await self._make_request("GET", endpoint)
            return emails.get('value', [])
        except Exception as e:
            return []

    async def create_draft_reply(self, initial_email, reply_text):
        """Create draft reply in Outlook with proper formatting"""
        try:
            if not self.token:
                await self.initialize()

            # Format the reply text with HTML
            formatted_html = self._create_html_email_message(reply_text)

            # Handle different input formats (dict or model)
            if isinstance(initial_email, dict):
                sender = initial_email.get('sender')
                subject = initial_email.get('subject', '')
            else:
                sender = getattr(initial_email, 'sender', '')
                subject = getattr(initial_email, 'subject', '')

            message = {
                "subject": f"Re: {subject}" if not subject.startswith("Re: ") else subject,
                "body": {
                    "contentType": "HTML",
                    "content": formatted_html
                },
                "toRecipients": [{
                    "emailAddress": {
                        "address": sender
                    }
                }]
            }

            # Create draft in drafts folder
            endpoint = f"/users/{self.email_address}/messages"
            response = await self._make_request("POST", endpoint, payload=message)
            
            if response:
                return {
                    "id": response.get("id", ""),
                    "threadId": response.get("conversationId", ""),
                    "messageId": response.get("internetMessageId", "")
                }
            return None

        except Exception as e:
            print(f"Error creating draft reply: {str(e)}")
            return None

    async def send_email(self, from_email, to_emails, subject, body):
        """Send an email"""
        try:
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body
                    },
                    "toRecipients": [{"emailAddress": {"address": email}} for email in to_emails]
                },
                "saveToSentItems": "true"
            }
            endpoint = f"/users/{from_email}/sendMail"
            return await self._make_request("POST", endpoint, payload=message)
        except Exception as e:
            return None

    async def fetch_draft_replies(self):
        """Fetch draft emails from Outlook"""
        try:
            endpoint = f"/users/{self.email_address}/mailFolders/drafts/messages"
            drafts = await self._make_request("GET", endpoint)
            return drafts.get('value', [])
        except Exception as e:
            return []

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
            # Close any pending connections
            await asyncio.sleep(0.25)
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry"""
        await self._get_session()
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()