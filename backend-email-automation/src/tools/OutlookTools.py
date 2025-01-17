import os
import ssl
import certifi
import aiohttp
from msal import ConfidentialClientApplication
from .base_email_tool import BaseEmailTool
from aiohttp import web
import webbrowser
import asyncio
from urllib.parse import urlencode

class OutlookTools(BaseEmailTool):
    def __init__(self, client_id, client_secret, tenant_id):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.session = None
        self.email_address = None
        self.token = None
        self.app = None
        
    async def initialize(self):
        """Initialize the OAuth2 flow and get access token"""
        self.token = await self._get_access_token()
        
    def _create_msal_app(self):
        """Create MSAL confidential client application"""
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        return ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret
        )

    async def _get_auth_code(self):
        """Get authorization code through local web server"""
        # Create MSAL app
        self.app = self._create_msal_app()
        
        # Authorization URL parameters
        auth_params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': 'http://localhost:8000/callback',
            'scope': 'https://graph.microsoft.com/Mail.ReadWrite',
            'response_mode': 'query'
        }
        
        # Construct authorization URL
        auth_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize?{urlencode(auth_params)}"
        
        # Store auth code
        auth_code = None
        
        # Create local server to handle callback
        async def handle_callback(request):
            nonlocal auth_code
            auth_code = request.query.get('code')
            return web.Response(text="Authentication successful! You can close this window.")
        
        # Setup server
        app = web.Application()
        app.router.add_get('/callback', handle_callback)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8000)
        await site.start()
        
        # Open browser for auth
        print("Opening browser for authentication...")
        webbrowser.open(auth_url)
        
        # Wait for auth code
        while auth_code is None:
            await asyncio.sleep(1)
            
        # Cleanup server
        await runner.cleanup()
        
        return auth_code

    async def _get_access_token(self):
        """Get access token using authorization code flow"""
        try:
            # Get authorization code
            auth_code = await self._get_auth_code()
            
            # Get token using auth code
            result = self.app.acquire_token_by_authorization_code(
                code=auth_code,
                scopes=["https://graph.microsoft.com/Mail.ReadWrite"],
                redirect_uri="http://localhost:8000/callback"
            )
            
            if "access_token" in result:
                print("Token obtained successfully!")
                return result["access_token"]
            else:
                print("Token acquisition failed!")
                print("Error:", result.get("error"))
                raise Exception(f"Could not obtain access token: {result.get('error_description')}")
                
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            raise

    async def _get_session(self):
        """Get or create aiohttp session with SSL context"""
        if self.session is None or self.session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session

    async def _make_request(self, method, endpoint, payload=None):
        """Make async request to Microsoft Graph API"""
        if not self.email_address:
            raise ValueError("email_address must be set before making requests")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        
        try:
            async with session.request(method, url, headers=headers, json=payload, ssl=False) as response:
                if response.status in [200, 201]:
                    return await response.json()
                else:
                    text = await response.text()
                    raise Exception(f"Error: {response.status}, {text}")
        except Exception as e:
            print(f"Request error for {url}: {str(e)}")
            raise

    async def fetch_unanswered_emails(self, max_results=50):
        """Fetch unanswered emails from Outlook"""
        try:
            endpoint = f"/users/{self.email_address}/messages?$top={max_results}&$orderby=receivedDateTime desc"
            emails = await self._make_request("GET", endpoint)
            return emails.get('value', [])
        except Exception as e:
            print(f"Error fetching Outlook emails: {e}")
            return []

    async def create_draft_reply(self, initial_email, reply_text):
        """Create draft reply in Outlook"""
        try:
            message = {
                "subject": f"Re: {initial_email['subject']}",
                "body": {
                    "contentType": "HTML",
                    "content": reply_text
                },
                "toRecipients": [{"emailAddress": {"address": initial_email['sender']}}]
            }
            endpoint = f"/users/{self.email_address}/messages"
            return await self._make_request("POST", endpoint, payload=message)
        except Exception as e:
            print(f"Error creating draft: {e}")
            return None

    async def send_reply(self, initial_email, reply_text):
        """Send reply using Outlook"""
        try:
            message = {
                "message": {
                    "subject": f"Re: {initial_email['subject']}",
                    "body": {
                        "contentType": "HTML",
                        "content": reply_text
                    },
                    "toRecipients": [{"emailAddress": {"address": initial_email['sender']}}]
                },
                "saveToSentItems": "true"
            }
            endpoint = f"/users/{self.email_address}/sendMail"
            return await self._make_request("POST", endpoint, payload=message)
        except Exception as e:
            print(f"Error sending reply: {e}")
            return None

    async def fetch_draft_replies(self):
        """Fetch draft emails from Outlook"""
        try:
            endpoint = f"/users/{self.email_address}/mailFolders/drafts/messages"
            drafts = await self._make_request("GET", endpoint)
            return drafts.get('value', [])
        except Exception as e:
            print(f"Error fetching drafts: {e}")
            return []

    async def cleanup(self):
        """Cleanup resources"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            # Wait for any pending requests to complete
            await asyncio.sleep(0.1)

    async def __aenter__(self):
        """Async context manager entry"""
        await self._get_session()
        await self.initialize()  # Initialize OAuth flow
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()