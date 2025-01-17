from enum import Enum
from colorama import Fore, Style
from typing import Optional
from .agents import Agents
from .state import GraphState, Email
from .tools.GmailTools import GmailToolsClass
from .tools.enhanced_outlook_tools import EnhancedOutlookTools

class EmailServiceType(Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"

class EmailServiceDetector:
    """Detects the type of email service based on email address"""
    @staticmethod
    def detect_service(email_address: str) -> EmailServiceType:
        email_domain = email_address.lower().split('@')[1]
        
        if 'gmail.com' in email_domain:
            return EmailServiceType.GMAIL
        elif any(domain in email_domain for domain in ['outlook.com', 'hotmail.com', 'live.com']):
            return EmailServiceType.OUTLOOK
        else:
            # For custom domains, default to Gmail
            return EmailServiceType.GMAIL

class EmailTools:
    """Unified interface for email operations"""
    def __init__(self, email_address: str):
        self.email_address = email_address
        self.service_type = EmailServiceDetector.detect_service(email_address)
        
        if self.service_type == EmailServiceType.GMAIL:
            self.service = GmailToolsClass()
        else:
            self.service = EnhancedOutlookTools(email_address)

    async def fetch_unanswered_emails(self, max_results=50):
        """Fetch unanswered emails from either service"""
        try:
            return await self.service.fetch_unanswered_emails(max_results)
        except Exception as e:
            print(f"Error fetching emails: {e}")
            return []

    async def create_draft_reply(self, initial_email, reply_text):
        """Create draft reply in either service"""
        try:
            return await self.service.create_draft_reply(initial_email, reply_text)
        except Exception as e:
            print(f"Error creating draft: {e}")
            return None

    async def send_reply(self, initial_email, reply_text):
        """Send reply using either service"""
        try:
            return await self.service.send_reply(initial_email, reply_text)
        except Exception as e:
            print(f"Error sending reply: {e}")
            return None

    async def fetch_draft_replies(self):
        """Fetch draft replies from either service"""
        try:
            return await self.service.fetch_draft_replies()
        except Exception as e:
            print(f"Error fetching drafts: {e}")
            return []

class Nodes:
    def __init__(self, email_address: str):
        """Initialize Nodes with email service detection"""
        self.agents = Agents()
        self.email_address = email_address
        self.email_tools = EmailTools(email_address)
        print(f"{Fore.CYAN}Initialized email service: {self.email_tools.service_type.value}{Style.RESET_ALL}")

    async def load_new_emails(self, state: GraphState) -> GraphState:
        """Load new emails from configured provider"""
        print(Fore.YELLOW + f"Loading new emails from {self.email_tools.service_type.value}...\n" + Style.RESET_ALL)
        try:
            emails = await self.email_tools.fetch_unanswered_emails()
            if not emails:
                return {"emails": []}
            return {"emails": [Email(**email) for email in emails]}
        except Exception as e:
            print(Fore.RED + f"Error loading emails: {str(e)}" + Style.RESET_ALL)
            return {"emails": []}

    def check_new_emails(self, state: GraphState) -> str:
        """Check if there are new emails to process"""
        if len(state['emails']) == 0:
            print(Fore.RED + "No new emails to process" + Style.RESET_ALL)
            return "empty"
        print(Fore.GREEN + f"Found {len(state['emails'])} new emails to process" + Style.RESET_ALL)
        return "process"

    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        """Check if email inbox is empty"""
        return state

    def categorize_email(self, state: GraphState) -> GraphState:
        """Categorizes the current email using the categorize_email agent."""
        print(Fore.YELLOW + "Checking email category...\n" + Style.RESET_ALL)
        
        # Get the last email
        current_email = state["emails"][-1]
        result = self.agents.categorize_email.invoke({"email": current_email.body})
        print(Fore.MAGENTA + f"Email category: {result.category.value}" + Style.RESET_ALL)
        
        return {
            "email_category": result.category.value,
            "current_email": current_email
        }

    def route_email_based_on_category(self, state: GraphState) -> str:
        """Routes the email based on its category."""
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)
        category = state["email_category"]
        if category == "product_enquiry":
            return "product related"
        elif category == "unrelated":
            return "unrelated"
        else:
            return "not product related"

    def construct_rag_queries(self, state: GraphState) -> GraphState:
        """Constructs RAG queries based on the email content."""
        print(Fore.YELLOW + "Designing RAG query...\n" + Style.RESET_ALL)
        email_content = state["current_email"].body
        query_result = self.agents.design_rag_queries.invoke({"email": email_content})
        
        return {"rag_queries": query_result.queries}

    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """Retrieves information from internal knowledge based on RAG questions."""
        print(Fore.YELLOW + "Retrieving information from internal knowledge...\n" + Style.RESET_ALL)
        final_answer = ""
        for query in state["rag_queries"]:
            rag_result = self.agents.generate_rag_answer.invoke(query)
            final_answer += query + "\n" + rag_result + "\n\n"
        
        return {"retrieved_documents": final_answer}

    def write_draft_email(self, state: GraphState) -> GraphState:
        """Writes a draft email based on the current email and retrieved information."""
        print(Fore.YELLOW + "Writing draft email...\n" + Style.RESET_ALL)
        
        # Format input to the writer agent
        inputs = (
            f'# **EMAIL CATEGORY:** {state["email_category"]}\n\n'
            f'# **EMAIL CONTENT:**\n{state["current_email"].body}\n\n'
            f'# **INFORMATION:**\n{state.get("retrieved_documents", "")}' # Empty for feedback or complaint
        )
        
        # Get messages history for current email
        writer_messages = state.get('writer_messages', [])
        
        # Write email
        draft_result = self.agents.email_writer.invoke({
            "email_information": inputs,
            "history": writer_messages
        })
        email = draft_result.email
        trials = state.get('trials', 0) + 1

        # Append writer's draft to the message list
        writer_messages.append(f"**Draft {trials}:**\n{email}")

        return {
            "generated_email": email, 
            "trials": trials,
            "writer_messages": writer_messages
        }

    def verify_generated_email(self, state: GraphState) -> GraphState:
        """Verifies the generated email using the proofreader agent."""
        print(Fore.YELLOW + "Verifying generated email...\n" + Style.RESET_ALL)
        review = self.agents.email_proofreader.invoke({
            "initial_email": state["current_email"].body,
            "generated_email": state["generated_email"],
        })

        writer_messages = state.get('writer_messages', [])
        writer_messages.append(f"**Proofreader Feedback:**\n{review.feedback}")

        return {
            "sendable": review.send,
            "writer_messages": writer_messages
        }

    def must_rewrite(self, state: GraphState) -> str:
        """Determines if the email needs to be rewritten based on the review and trial count."""
        email_sendable = state["sendable"]
        if email_sendable:
            print(Fore.GREEN + "Email is good, ready to be sent!!!" + Style.RESET_ALL)
            state["emails"].pop()
            state["writer_messages"] = []
            return "send"
        elif state["trials"] >= 3:
            print(Fore.RED + "Email is not good, we reached max trials must stop!!!" + Style.RESET_ALL)
            state["emails"].pop()
            state["writer_messages"] = []
            return "stop"
        else:
            print(Fore.RED + "Email is not good, must rewrite it..." + Style.RESET_ALL)
            return "rewrite"

    async def create_draft_response(self, state: GraphState) -> GraphState:
        """Create draft response in email system"""
        print(Fore.YELLOW + "Creating email draft...\n" + Style.RESET_ALL)
        try:
            await self.email_tools.create_draft_reply(
                state["current_email"],
                state["generated_email"]
            )
            print(Fore.GREEN + "Draft created successfully" + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f"Error creating draft: {str(e)}" + Style.RESET_ALL)
        return {"retrieved_documents": "", "trials": 0}

    async def send_email_response(self, state: GraphState) -> GraphState:
        """Send the email response"""
        print(Fore.YELLOW + "Sending email...\n" + Style.RESET_ALL)
        try:
            await self.email_tools.send_reply(
                state["current_email"],
                state["generated_email"]
            )
            print(Fore.GREEN + "Email sent successfully" + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f"Error sending email: {str(e)}" + Style.RESET_ALL)
        return {"retrieved_documents": "", "trials": 0}

    def skip_unrelated_email(self, state: GraphState) -> GraphState:
        """Skip processing for unrelated emails"""
        print(Fore.YELLOW + "Skipping unrelated email...\n" + Style.RESET_ALL)
        state["emails"].pop()
        print(Fore.GREEN + "Email skipped" + Style.RESET_ALL)
        return state