# main.py
import asyncio
from colorama import Fore, Style
from src.graph import Workflow
import traceback
from config import config_manager

# Get configuration
config = config_manager.get_config()

# Config for workflow
workflow_config = {'recursion_limit': 100}

# Validate configuration
validation_result = config_manager.validate_config()

# Check required configurations
if not validation_result['gmail_configured']:
    print(Fore.YELLOW + "Warning: Gmail is not properly configured" + Style.RESET_ALL)
if not validation_result['outlook_configured']:
    print(Fore.YELLOW + "Warning: Outlook is not properly configured" + Style.RESET_ALL)
if not validation_result['ai_configured']:
    print(Fore.YELLOW + "Warning: AI services are not properly configured" + Style.RESET_ALL)

async def run_workflow(service: str = 'gmail'):
    """Run workflow for specified email service"""
    try:
        # Select appropriate email based on service
        if service == 'gmail':
            email = config.gmail.email
            print(Fore.YELLOW + f"Using Gmail: {email}" + Style.RESET_ALL)
        else:
            email = config.outlook.email
            print(Fore.YELLOW + f"Using Outlook: {email}" + Style.RESET_ALL)

        # Initialize workflow
        workflow = Workflow(service)
        app = workflow.app

        initial_state = {
            "emails": [],
            "current_email": None,
            "email_category": "",
            "generated_email": "",
            "rag_queries": [],
            "retrieved_documents": "",
            "writer_messages": [],
            "sendable": False,
            "trials": 0
        }

        print(Fore.GREEN + f"Starting {service} workflow..." + Style.RESET_ALL)
        async for output in app.astream(initial_state, workflow_config):
            for key, value in output.items():
                print(Fore.CYAN + f"Finished running: {key}" + Style.RESET_ALL)

    except Exception as e:
        print(Fore.RED + f"Error in {service} workflow: {str(e)}" + Style.RESET_ALL)
        print(Fore.RED + "Traceback:" + Style.RESET_ALL)
        traceback.print_exc()
        raise e
    finally:
        if 'workflow' in locals() and hasattr(workflow, 'nodes'):
            await workflow.nodes.cleanup()

async def main():
    """Main function to handle command line arguments"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--service', choices=['gmail', 'outlook'], default='gmail',
                       help='Email service to use')
    args = parser.parse_args()
    
    await run_workflow(args.service)

if __name__ == "__main__":
    asyncio.run(main())