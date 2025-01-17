import os
import re
import uuid
import base64
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from .base_email_tool import BaseEmailTool
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class GmailToolsClass(BaseEmailTool):
    def __init__(self):
        self.service = self._get_gmail_service()
        self._executor = ThreadPoolExecutor(max_workers=5)

    def fetch_recent_emails(self, hours=24, max_results=500):
        """
        Public method to fetch recent emails - required by the API.
        Direct synchronous wrapper around fetch_recent_emails_sync.
        """
        return self.fetch_recent_emails_sync(hours=hours, max_results=max_results)

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous functions asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, 
            partial(func, *args, **kwargs)
        )

    async def fetch_unanswered_emails(self, max_results=50):
        """
        Async wrapper for fetching unanswered emails.
        """
        def _fetch():
            try:
                recent_emails = self.fetch_recent_emails_sync(max_results)
                if not recent_emails: 
                    return []
                
                drafts = self._fetch_draft_replies_sync()
                threads_with_drafts = {draft['threadId'] for draft in drafts}

                seen_threads = set()
                unanswered_emails = []
                for email in recent_emails:
                    thread_id = email['threadId']
                    labels = email.get('labelIds', [])
                    
                    # Skip if: already seen, has drafts, not unread, or is draft/sent
                    if (thread_id in seen_threads or 
                        thread_id in threads_with_drafts or 
                        'UNREAD' not in labels or
                        any(label in labels for label in ['DRAFT', 'SENT'])):
                        continue

                    seen_threads.add(thread_id)
                    email_info = self._get_email_info(email['id'])
                    
                    if self._should_skip_email(email_info):
                        continue
                        
                    unanswered_emails.append(email_info)
                
                return unanswered_emails
            except Exception as e:
                print(f"An error occurred: {e}")
                return []

        return await self._run_sync(_fetch)

    def fetch_recent_emails_sync(self, hours=24, max_results=500):
        """Synchronous version of fetch_recent_emails"""
        try:
            now = datetime.now()
            delay = now - timedelta(hours=hours)
            query = f'after:{int(delay.timestamp())} in:inbox'
            
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get("messages", [])
            
            if messages:
                detailed_messages = []
                for message in messages:
                    msg_detail = self.service.users().messages().get(
                        userId="me",
                        id=message['id'],
                        format='full'
                    ).execute()
                    detailed_messages.append(msg_detail)
                return detailed_messages
            
            return []
        
        except Exception as error:
            print(f"An error occurred while fetching emails: {error}")
            return []

    async def create_draft_reply(self, initial_email, reply_text):
        """Async wrapper for creating draft replies"""
        def _create_draft():
            try:
                message = self._create_reply_message(initial_email, reply_text)
                return self.service.users().drafts().create(
                    userId="me", body={"message": message}
                ).execute()
            except Exception as error:
                print(f"An error occurred while creating draft: {error}")
                return None

        return await self._run_sync(_create_draft)

    async def send_reply(self, initial_email, reply_text):
        """Async wrapper for sending replies"""
        def _send():
            try:
                message = self._create_reply_message(initial_email, reply_text, send=True)
                return self.service.users().messages().send(
                    userId="me", body=message
                ).execute()
            except Exception as error:
                print(f"An error occurred while sending reply: {error}")
                return None

        return await self._run_sync(_send)

    def fetch_draft_replies(self):
        """
        Synchronous method to fetch draft replies - required by the API.
        """
        try:
            drafts = self.service.users().drafts().list(userId="me").execute()
            draft_list = drafts.get("drafts", [])
            return [
                {
                    "draft_id": draft["id"],
                    "threadId": draft["message"]["threadId"],
                    "id": draft["message"]["id"],
                }
                for draft in draft_list
            ]
        except Exception as error:
            print(f"An error occurred while fetching drafts: {error}")
            return []

    async def fetch_draft_replies_async(self):
        """
        Async version of fetch_draft_replies for async contexts
        """
        return await self._run_sync(self.fetch_draft_replies)

    def _fetch_draft_replies_sync(self):
        """Private method to fetch drafts - used internally"""
        return self.fetch_draft_replies()

    def _get_gmail_service(self):
        """Initialize and get Gmail service"""
        creds = None
        if os.path.exists('/app/token.json'):
            creds = Credentials.from_authorized_user_file('/app/token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('/app/credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('/app/token.json', 'w') as token:
                token.write(creds.to_json())
        
        return build('gmail', 'v1', credentials=creds)
    
    def _should_skip_email(self, email_info):
        """Check if email should be skipped"""
        return os.environ['MY_EMAIL'] in email_info['sender']

    def _get_email_info(self, msg_id):
        """Get detailed email information"""
        message = self.service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        payload = message.get('payload', {})
        headers = {header["name"].lower(): header["value"] for header in payload.get("headers", [])}
        
        # Get labels to check read/unread status
        labels = message.get('labelIds', [])
        is_unread = 'UNREAD' in labels
        
        return {
            "id": msg_id,
            "threadId": message.get("threadId"),
            "messageId": headers.get("message-id"),
            "references": headers.get("references", ""),
            "sender": headers.get("from", "Unknown"),
            "subject": headers.get("subject", "No Subject"),
            "body": self._get_email_body(payload),
            "isUnread": is_unread,
            "labels": labels
        }

    def _create_reply_message(self, email, reply_text, send=False):
        """Create a reply message with proper headers and format"""
        message = self._create_html_email_message(
            recipient=email.sender,
            subject=email.subject,
            reply_text=reply_text
        )

        if email.messageId:
            message["In-Reply-To"] = email.messageId
            message["References"] = f"{email.references} {email.messageId}".strip()
            
            if send:
                message["Message-ID"] = f"<{uuid.uuid4()}@gmail.com>"
                
        body = {
            "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
            "threadId": email.threadId
        }

        return body
    
    def _get_email_body(self, payload):
        """Extract and process email body content"""
        def decode_data(data):
            return base64.urlsafe_b64decode(data).decode('utf-8').strip() if data else ""

        def extract_body(parts):
            for part in parts:
                mime_type = part.get('mimeType', '')
                data = part['body'].get('data', '')
                if mime_type == 'text/plain':
                    return decode_data(data)
                if mime_type == 'text/html':
                    html_content = decode_data(data)
                    return self._extract_main_content_from_html(html_content)
                if 'parts' in part:
                    result = extract_body(part['parts'])
                    if result:
                        return result
            return ""

        if 'parts' in payload:
            body = extract_body(payload['parts'])
        else:
            data = payload['body'].get('data', '')
            body = decode_data(data)
            if payload.get('mimeType') == 'text/html':
                body = self._extract_main_content_from_html(body)

        return self._clean_body_text(body)

    def _extract_main_content_from_html(self, html_content):
        """Extract text content from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'title']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)

    def _clean_body_text(self, text):
        """Clean and normalize text content"""
        return re.sub(r'\s+', ' ', text.replace('\r', '').replace('\n', '')).strip()
    
    def _create_html_email_message(self, recipient, subject, reply_text):
        """Create HTML formatted email message"""
        message = MIMEMultipart("alternative")
        message["to"] = recipient
        message["subject"] = f"Re: {subject}" if not subject.startswith("Re: ") else subject

        html_text = reply_text.replace("\n", "<br>").replace("\\n", "<br>")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>{html_text}</body>
        </html>
        """

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        return message

    async def cleanup(self):
        """Cleanup method for the thread pool executor"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    async def __aenter__(self):
        """Async context manager entry"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=5)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()