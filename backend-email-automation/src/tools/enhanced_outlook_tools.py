from .OutlookTools import OutlookTools
from datetime import datetime, timedelta, timezone
from config import config_manager 

class EnhancedOutlookTools(OutlookTools):
    def __init__(self, email_address):
        config = config_manager.get_config()

        client_id = config.outlook.client_id
        client_secret = config.outlook.client_secret
        tenant_id = config.outlook.tenant_id
        
        # Validate credentials
        if not all([client_id, client_secret, tenant_id]):
            raise ValueError("Missing required Outlook credentials in configuration")
            
        # Initialize base class
        super().__init__(client_id, client_secret, tenant_id)
        self.email_address = email_address
    
    async def fetch_unanswered_emails(self, max_results=50):
        """Fetch unanswered emails from Outlook with standardized format"""
        try:
            if not self.token:
                await self.initialize()

            # Calculate recent timeframe
            now = datetime.utcnow()
            time_ago = now - timedelta(hours=24)  # Last 24 hours
            
            # Get inbox folder ID first
            folder_endpoint = f"/users/{self.email_address}/mailFolders/inbox"
            folder_response = await self._make_request("GET", folder_endpoint)
            folder_id = folder_response.get('id')
            
            if not folder_id:
                return []

            # Build query for unread messages in inbox
            filter_query = (
                f"receivedDateTime ge {time_ago.isoformat()}Z "
                f"and parentFolderId eq '{folder_id}' "
                "and isRead eq false"
            )

            # Fetch messages with necessary fields
            endpoint = (
                f"/users/{self.email_address}/messages?"
                f"$filter={filter_query}&"
                "$orderby=receivedDateTime desc&"
                f"$top={str(max_results)}&"
                "$select=id,conversationId,internetMessageId,from,subject,body,isRead"
            )

            response = await self._make_request("GET", endpoint)
            emails = response.get('value', [])

            # Transform to standardized format
            standardized_emails = []
            for email in emails:
                if not self._should_skip_email(email):
                    email_body = email.get("body", {}).get("content", "")
                    if email.get("body", {}).get("contentType", "").lower() == "html":
                        # Strip HTML tags for plain text
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(email_body, 'html.parser')
                        email_body = soup.get_text(separator=' ', strip=True)

                    standardized_email = {
                        "id": email.get("id", ""),
                        "threadId": email.get("conversationId", "") or str(email.get("id", "")),
                        "messageId": email.get("internetMessageId", "") or str(email.get("id", "")),
                        "references": email.get("conversationId", "") or str(email.get("id", "")),
                        "sender": email.get("from", {}).get("emailAddress", {}).get("address", ""),
                        "subject": email.get("subject", "No Subject"),
                        "body": email_body,
                        "isUnread": not email.get("isRead", True),
                        "labels": []
                    }
                    standardized_emails.append(standardized_email)

            return standardized_emails

        except Exception as e:
            print(f"Error fetching unanswered emails: {str(e)}")
            return []
        
    async def fetch_recent_emails(self, hours=24, folder='inbox'):
        """Fetch recent emails from Outlook with improved filtering"""
        try:
            if not self.token:
                await self.initialize()

            # Calculate the time range
            now = datetime.utcnow()
            time_ago = now - timedelta(hours=hours)
            
            # First, get the folder ID for inbox
            folder_endpoint = f"/users/{self.email_address}/mailFolders/inbox"
            folder_response = await self._make_request("GET", folder_endpoint)
            folder_id = folder_response.get('id')
            
            if not folder_id:
                print("Could not get folder ID")
                return []

            # Build filter query with the actual folder ID
            filter_query = (
                f"receivedDateTime ge {time_ago.isoformat()}Z "
                f"and parentFolderId eq '{folder_id}'"
            )

            # Construct the endpoint with filter and essential fields
            endpoint = (
                f"/users/{self.email_address}/messages?"
                f"$filter={filter_query}&"
                "$orderby=receivedDateTime desc&"
                "$select=id,conversationId,subject,from,body,isRead,"
                "receivedDateTime,internetMessageId,parentFolderId"
            )
            
            try:
                response = await self._make_request("GET", endpoint)
                return response.get('value', [])
            except Exception as e:
                print(f"Error fetching emails: {str(e)}")
                return []

        except Exception as e:
            print(f"Error in fetch_recent_emails: {str(e)}")
            return []

    async def fetch_draft_replies(self):
        """Fetch only valid draft replies from Outlook"""
        try:
            if not self.token:
                await self.initialize()

            # Get drafts folder first
            drafts_folder_endpoint = f"/users/{self.email_address}/mailFolders/drafts"
            drafts_folder = await self._make_request("GET", drafts_folder_endpoint)
            drafts_folder_id = drafts_folder.get('id')

            if not drafts_folder_id:
                print("Could not get drafts folder ID")
                return []

            # Build query to get only valid drafts
            filter_query = (
                f"parentFolderId eq '{drafts_folder_id}' "
                "and isDraft eq true "
                "and startsWith(subject, 'RE: ')"
            )

            # Get messages with specific fields we need
            endpoint = (
                f"/users/{self.email_address}/messages?"
                f"$filter={filter_query}&"
                "$select=id,conversationId,subject,isDraft,parentFolderId"
            )

            response = await self._make_request("GET", endpoint)
            if not response:
                return []

            drafts = response.get('value', [])

            # Additional filtering to ensure we only count valid drafts
            valid_drafts = [
                draft for draft in drafts
                if (
                    draft.get('isDraft', False) and
                    draft.get('parentFolderId') == drafts_folder_id and
                    draft.get('subject', '').lower().startswith('re: ') and
                    not draft.get('isDeleted', False)
                )
            ]

            return valid_drafts

        except Exception as e:
            print(f"Error fetching draft replies: {str(e)}")
            return []

    async def get_reply_count(self, hours=24):
        """Get accurate count of replied messages in Outlook"""
        try:
            if not self.token:
                await self.initialize()

            # Get sent items folder first
            sent_folder_endpoint = f"/users/{self.email_address}/mailFolders/sentitems"
            sent_folder = await self._make_request("GET", sent_folder_endpoint)
            sent_folder_id = sent_folder.get('id')

            if not sent_folder_id:
                print("Could not get sent items folder ID")
                return 0

            # Calculate time range
            now = datetime.utcnow()
            time_ago = now - timedelta(hours=hours)

            # Build query to get sent items in the time range
            filter_query = (
                f"sentDateTime ge {time_ago.isoformat()}Z "
                f"and parentFolderId eq '{sent_folder_id}' "
                "and startsWith(subject, 'RE: ')"
            )

            # Get sent replies
            endpoint = (
                f"/users/{self.email_address}/messages?"
                f"$filter={filter_query}&"
                "$select=id,conversationId,subject,sentDateTime,parentFolderId"
            )

            response = await self._make_request("GET", endpoint)
            sent_replies = response.get('value', [])

            # Count unique conversations that have replies
            replied_conversations = set(
                msg['conversationId'] 
                for msg in sent_replies 
                if msg.get('conversationId')
            )

            return len(replied_conversations)

        except Exception as e:
            print(f"Error counting replies: {str(e)}")
            return 0

    # Helper methods
    def _should_skip_email(self, email):
        """Check if email should be skipped"""
        try:
            sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
            return self.email_address.lower() in sender.lower()
        except Exception as e:
            return True

    def _get_email_info(self, email):
        """Convert Outlook email format to standard format"""
        try:
            if not email or not isinstance(email, dict):
                return None
                
            return {
                "id": email.get("id", ""),
                "threadId": email.get("conversationId", ""),
                "messageId": email.get("internetMessageId", ""),
                "references": email.get("conversationId", ""),
                "sender": email.get("from", {}).get("emailAddress", {}).get("address", "Unknown"),
                "subject": email.get("subject", "No Subject"),
                "body": email.get("body", {}).get("content", "").strip(),
                "isUnread": not email.get("isRead", False),
                "labels": email.get("categories", [])
            }
        except Exception as e:
            print(f"Error formatting email info: {str(e)}")
            return None
        
    def _create_html_email_message(self, text):
        """Create HTML formatted content with proper but compact spacing"""
        parts = text.strip().split('\n\n')
        formatted_parts = []
        for part in parts:
            formatted_part = part.replace('\n', '<br>')
            formatted_parts.append(f"<p>{formatted_part}</p>")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #000000;
                    margin: 0;
                    padding: 0.5em;
                }}
                p {{ 
                    margin: 0.8em 0;
                    padding: 0;
                }}
                .signature {{
                    margin-top: 1em;
                }}
            </style>
        </head>
        <body>
            {'\n'.join(formatted_parts)}
        </body>
        </html>
        """
        return html_content.strip()

    async def send_email(self, from_email, to_emails, subject, body):
        """Send an email"""
        try:
            formatted_html = self._create_html_email_message(body)
            
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": formatted_html
                    },
                    "toRecipients": [{"emailAddress": {"address": email}} for email in to_emails]
                },
                "saveToSentItems": "true"
            }
            endpoint = f"/users/{from_email}/sendMail"
            return await self._make_request("POST", endpoint, payload=message)
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return None

    async def send_reply(self, initial_email, reply_text):
        """Send a reply email using Outlook"""
        try:
            if not self.token:
                await self.initialize()

            formatted_html = self._create_html_email_message(reply_text)
            return await self.send_email(
                from_email=self.email_address,
                to_emails=[initial_email.sender],
                subject=f"Re: {initial_email.subject}",
                body=formatted_html
            )
        except Exception as e:
            print(f"Error sending reply: {str(e)}")
            return None

    async def check_if_replied(self, message_id):
        """Check if a specific message has been replied to"""
        try:
            if not self.token:
                await self.initialize()

            message = await self._make_request("GET", 
                f"/users/{self.email_address}/messages/{message_id}?"
                "$select=conversationId"
            )
            
            conversation_id = message.get('conversationId')
            if not conversation_id:
                return False

            conversation_messages = await self._make_request("GET",
                f"/users/{self.email_address}/messages?"
                f"$filter=conversationId eq '{conversation_id}'&"
                "$select=sender,subject,sentDateTime"
            )

            user_replies = [
                msg for msg in conversation_messages.get('value', [])
                if (msg.get('sender', {}).get('emailAddress', {}).get('address', '').lower() 
                    == self.email_address.lower()
                    and msg.get('subject', '').lower().startswith('re: '))
            ]

            return len(user_replies) > 0

        except Exception as e:
            print(f"Error checking reply status: {str(e)}")
            return False
        
    async def create_draft_reply(self, initial_email, reply_text):
        """Create draft reply in Outlook with proper conversation threading"""
        try:
            if not self.token:
                await self.initialize()

            # Format the reply text with HTML
            formatted_html = self._create_html_email_message(reply_text)

            # Handle different input formats (dict or model)
            if isinstance(initial_email, dict):
                sender = initial_email.get('sender')
                subject = initial_email.get('subject', '')
                thread_id = initial_email.get('threadId', '')
                original_id = initial_email.get('id', '')
            else:
                sender = getattr(initial_email, 'sender', '')
                subject = getattr(initial_email, 'subject', '')
                thread_id = getattr(initial_email, 'threadId', '')
                original_id = getattr(initial_email, 'id', '')

            # Ensure proper subject prefix
            if not subject.lower().startswith('re:'):
                subject = f"Re: {subject}"

            # Create the draft message
            message = {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": formatted_html
                },
                "toRecipients": [{
                    "emailAddress": {
                        "address": sender
                    }
                }],
                "conversationId": thread_id
            }

            # If we have the original message ID, create reply using replyTo endpoint
            if original_id:
                try:
                    # First, create a draft reply using the replyTo endpoint
                    reply_endpoint = f"/users/{self.email_address}/messages/{original_id}/createReply"
                    reply_response = await self._make_request("POST", reply_endpoint)
                    
                    if reply_response and reply_response.get('id'):
                        # Update the draft content
                        update_endpoint = f"/users/{self.email_address}/messages/{reply_response['id']}"
                        update_payload = {
                            "body": message["body"]
                        }
                        
                        await self._make_request("PATCH", update_endpoint, payload=update_payload)
                        
                        return {
                            "id": reply_response.get("id", ""),
                            "threadId": reply_response.get("conversationId", thread_id),
                            "messageId": reply_response.get("internetMessageId", "")
                        }
                except Exception as reply_error:
                    print(f"Error using replyTo endpoint: {str(reply_error)}")
                    # Fall back to creating a new draft
                    pass

            # If replyTo failed or we don't have original_id, create a new draft
            endpoint = f"/users/{self.email_address}/messages"
            response = await self._make_request("POST", endpoint, payload=message)
            
            if response:
                return {
                    "id": response.get("id", ""),
                    "threadId": response.get("conversationId", thread_id),
                    "messageId": response.get("internetMessageId", "")
                }
                
            return None

        except Exception as e:
            print(f"Error creating draft reply: {str(e)}")
            return None