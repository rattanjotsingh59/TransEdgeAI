import asyncio
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import config_manager
from src.tools.GmailTools import GmailToolsClass
from src.tools.enhanced_outlook_tools import EnhancedOutlookTools
from datetime import datetime, timedelta
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = config_manager.get_config()

app = FastAPI(
    title="Email Automation",
    version="1.0",
    description="Email Automation API",
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

class EmailServiceType(Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"

class EmailToolFactory:
    @staticmethod
    def create_email_tool(service_type: EmailServiceType):
        try:
            if service_type == EmailServiceType.GMAIL:
                return GmailToolsClass()
            elif service_type == EmailServiceType.OUTLOOK:
                return EnhancedOutlookTools(config.outlook.email)
        except Exception as e:
            logger.error(f"Error creating email tool: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/email-stats")
async def get_email_stats(
    service: str = Query(..., pattern="^(gmail|outlook)$"),
    hours: int = Query(default=24, ge=1),
    account: Optional[str] = None
):
    """
    Get email statistics for the specified service and time range
    """
    try:
        # Initialize service and tools
        service_type = EmailServiceType(service)
        email_tools = EmailToolFactory.create_email_tool(service_type)
        
        # Initialize statistics
        stats = {
            "total": 0,
            "unread": 0,
            "read": 0,
            "replied": 0,
            "drafted": 0
        }
        
        # Fetch emails based on service type
        try:
            if service_type == EmailServiceType.GMAIL:
                # For Gmail
                recent_emails = email_tools.fetch_recent_emails(hours=hours)
                
                # Filter for inbox emails only
                inbox_emails = [
                    email for email in recent_emails 
                    if 'INBOX' in email.get('labelIds', []) and
                    'TRASH' not in email.get('labelIds', []) and
                    'DRAFT' not in email.get('labelIds', [])
                ]
                
                if inbox_emails:
                    # Calculate Gmail stats
                    stats["total"] = len(inbox_emails)
                    stats["unread"] = sum(1 for email in inbox_emails 
                                        if 'UNREAD' in email.get('labelIds', []))
                    stats["replied"] = sum(1 for email in inbox_emails 
                                         if any(label in email.get('labelIds', []) 
                                               for label in ['REPLIED', 'SENT']))
                    
                # Fetch Gmail drafts
                try:
                    drafts = email_tools.fetch_draft_replies()
                    stats["drafted"] = len(drafts)
                except Exception as draft_error:
                    logger.error(f"Error fetching Gmail drafts: {str(draft_error)}")
                
            else:
                # For Outlook
                # Fetch inbox messages
                inbox_emails = await email_tools.fetch_recent_emails(
                    hours=hours,
                    folder='inbox'
                )
                
                if inbox_emails:
                    # Calculate Outlook stats
                    stats["total"] = len(inbox_emails)
                    stats["unread"] = sum(1 for email in inbox_emails 
                                        if not email.get('isRead', True))
                    
                    # Get reply count using dedicated method
                    try:
                        stats["replied"] = await email_tools.get_reply_count(hours=hours)
                    except Exception as reply_error:
                        logger.error(f"Error getting Outlook reply count: {str(reply_error)}")
                
                # Fetch Outlook drafts
                    try:
                        drafts = await email_tools.fetch_draft_replies()
                        # Only count valid drafts that have content and are replies
                        stats["drafted"] = len([
                            draft for draft in drafts 
                            if draft.get('subject', '').lower().startswith('re:')
                        ])
                    except Exception as draft_error:
                        logger.error(f"Error fetching Outlook drafts: {str(draft_error)}")
                        stats["drafted"] = 0
                
            # Calculate read count based on total and unread
            stats["read"] = stats["total"] - stats["unread"]
            
        except Exception as fetch_error:
            logger.error(f"Error fetching emails: {str(fetch_error)}")
            # Stats will remain at their default values (all 0)
        
        # Time range warning for large queries
        if hours > 720:  # More than 30 days
            logger.warning(f"Large time range requested: {hours} hours")
        
        return stats
        
    except Exception as e:
        error_msg = f"Error processing email statistics: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
@app.get("/api/accounts")
async def get_accounts():
    """Get configured email accounts"""
    try:
        accounts = []
        
        # Check Gmail configuration
        if config.gmail.email:
            accounts.append({
                "email": config.gmail.email,
                "service": "gmail",
                "isConfigured": bool(config.gmail.credentials_file)
            })
            
        # Check Outlook configuration
        if config.outlook.email:
            accounts.append({
                "email": config.outlook.email,
                "service": "outlook",
                "isConfigured": bool(all([
                    config.outlook.client_id,
                    config.outlook.client_secret,
                    config.outlook.tenant_id
                ]))
            })
            
        return accounts
    except Exception as e:
        logger.error(f"Error getting accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/recent-emails")
async def get_recent_emails(
    service: str = Query(..., pattern="^(gmail|outlook)$"),
    hours: int = Query(default=24, ge=1),
    account: Optional[str] = None
):
    """
    Get recent emails for the specified service and time range
    """
    try:
        # Initialize service and tools
        service_type = EmailServiceType(service)
        email_tools = EmailToolFactory.create_email_tool(service_type)
        
        recent_emails = []
        
        try:
            if service_type == EmailServiceType.GMAIL:
                # For Gmail
                emails = email_tools.fetch_recent_emails(hours=hours)
                for email in emails:
                    if 'INBOX' in email.get('labelIds', []):
                        headers = {h['name'].lower(): h['value'] for h in email.get('payload', {}).get('headers', [])}
                        recent_emails.append({
                            "id": email['id'],
                            "subject": headers.get('subject', 'No Subject'),
                            "sender": headers.get('from', 'Unknown'),
                            "timestamp": email.get('internalDate'),
                            "isRead": 'UNREAD' not in email.get('labelIds', []),
                            "isStarred": 'STARRED' in email.get('labelIds', [])
                        })
            else:
                # For Outlook
                emails = await email_tools.fetch_recent_emails(hours=hours)
                for email in emails:
                    sender_info = email.get('from', {}).get('emailAddress', {})
                    recent_emails.append({
                        "id": email.get('id', ''),
                        "subject": email.get('subject', 'No Subject'),
                        "sender": f"{sender_info.get('name', '')} <{sender_info.get('address', 'Unknown')}>",
                        "timestamp": email.get('receivedDateTime', ''),
                        "isRead": email.get('isRead', False),
                        "isStarred": email.get('flag', {}).get('flagStatus', '') == 'flagged'
                    })
                    
            # Sort emails by timestamp
            recent_emails.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Limit to most recent 10 emails
            recent_emails = recent_emails[:10]
            
            # Format timestamps for consistent display
            for email in recent_emails:
                try:
                    if service_type == EmailServiceType.GMAIL:
                        # Convert Gmail's timestamp (milliseconds since epoch)
                        ts = int(email['timestamp']) / 1000
                        dt = datetime.fromtimestamp(ts)
                    else:
                        # Parse Outlook's ISO timestamp
                        dt = datetime.fromisoformat(email['timestamp'].replace('Z', '+00:00'))
                    
                    # Calculate relative time
                    now = datetime.now(dt.tzinfo)
                    diff = now - dt
                    
                    if diff.days > 0:
                        email['timestamp'] = f"{diff.days}d ago"
                    elif diff.seconds >= 3600:
                        hours = diff.seconds // 3600
                        email['timestamp'] = f"{hours}h ago"
                    else:
                        minutes = diff.seconds // 60
                        email['timestamp'] = f"{minutes}m ago"
                except Exception as e:
                    logger.error(f"Error formatting timestamp: {str(e)}")
                    email['timestamp'] = 'Unknown'
            
            return recent_emails
            
        except Exception as fetch_error:
            logger.error(f"Error fetching recent emails: {str(fetch_error)}")
            return []
        
    except Exception as e:
        error_msg = f"Error processing recent emails: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/health")
async def health_check():
    try:
        validation_result = config_manager.validate_config()
        
        return {
            "status": "healthy",
            "accounts": {
                "gmail": {
                    "email": config.gmail.email,
                    "configured": validation_result['gmail_configured']
                },
                "outlook": {
                    "email": config.outlook.email,
                    "configured": validation_result['outlook_configured']
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/email-search")
async def search_emails(
    service: str = Query(..., pattern="^(gmail|outlook)$"),
    search_term: str = Query(..., min_length=1),
    hours: int = Query(default=24, ge=1)  # Default to 24 hours
):
    """
    Search emails for specific sender/customer
    """
    try:
        service_type = EmailServiceType(service)
        email_tools = EmailToolFactory.create_email_tool(service_type)
        
        try:
            total_count = 0
            if service_type == EmailServiceType.GMAIL:
                # For Gmail
                emails = email_tools.fetch_recent_emails(hours=hours)
                for email in emails:
                    if 'INBOX' in email.get('labelIds', []):
                        headers = {h['name'].lower(): h['value'] for h in email.get('payload', {}).get('headers', [])}
                        from_header = headers.get('from', '').lower()
                        if search_term.lower() in from_header:
                            total_count += 1
            else:
                # For Outlook
                emails = await email_tools.fetch_recent_emails(hours=hours)
                for email in emails:
                    sender_info = email.get('from', {}).get('emailAddress', {})
                    sender_name = sender_info.get('name', '').lower()
                    sender_email = sender_info.get('address', '').lower()
                    if (search_term.lower() in sender_name or 
                        search_term.lower() in sender_email):
                        total_count += 1
            
            # Format the time period for response
            time_period = (
                f"{hours} hours" if hours < 24 
                else f"{hours // 24} days"
            )
            
            return {
                "count": total_count,
                "search_term": search_term,
                "hours_searched": hours,
                "time_period": time_period
            }
            
        except Exception as fetch_error:
            logger.error(f"Error searching emails: {str(fetch_error)}")
            raise HTTPException(status_code=500, detail=str(fetch_error))
        
    except Exception as e:
        error_msg = f"Error processing email search: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)