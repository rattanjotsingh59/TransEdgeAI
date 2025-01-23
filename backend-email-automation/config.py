from typing import Dict, Any
import os
import json
from dataclasses import dataclass

@dataclass
class OutlookConfig:
    client_id: str
    client_secret: str
    tenant_id: str
    email: str

@dataclass
class GmailConfig:
    email: str
    credentials_file: str
    user_email: str

@dataclass
class AIConfig:
    gemini_api_key: str

@dataclass
class Config:
    outlook: OutlookConfig
    gmail: GmailConfig
    ai: AIConfig
    environment: str

class ConfigurationManager:
    """Manages application configuration with support for different environments"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Config:
        """Load configuration based on environment"""
        env = os.getenv('APP_ENV', 'development')
        
        # Default/placeholder configuration - DO NOT PUT REAL VALUES HERE
        config_data = {
            'outlook': {
                'client_id': '<OUTLOOK_CLIENT_ID>',
                'client_secret': '<OUTLOOK_CLIENT_SECRET>',
                'tenant_id': '<OUTLOOK_TENANT_ID>',
                'email': '<OUTLOOK_EMAIL>'
            },
            'gmail': {
                'email': '<GMAIL_EMAIL>',
                'credentials_file': '<CREDENTIALS_FILE_PATH>',
                'user_email': '<USER_EMAIL>'
            },
            'ai': {
                'gemini_api_key': '<GEMINI_API_KEY>'
            },
            'environment': env
        }
        
        # Try to load from config file - THIS WILL CONTAIN YOUR REAL VALUES
        config_file = f'config.{env}.json'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config_data.update(file_config)
        
        # Override with environment variables if present
        outlook_config = OutlookConfig(
            client_id=os.getenv('OUTLOOK_CLIENT_ID', config_data['outlook']['client_id']),
            client_secret=os.getenv('OUTLOOK_CLIENT_SECRET', config_data['outlook']['client_secret']),
            tenant_id=os.getenv('OUTLOOK_TENANT_ID', config_data['outlook']['tenant_id']),
            email=os.getenv('OUTLOOK_EMAIL', config_data['outlook']['email'])
        )
        
        gmail_config = GmailConfig(
            email=os.getenv('GMAIL_EMAIL', config_data['gmail']['email']),
            credentials_file=os.getenv('GMAIL_CREDENTIALS_FILE', config_data['gmail']['credentials_file']),
            user_email=os.getenv('MY_EMAIL', config_data['gmail']['user_email'])
        )

        ai_config = AIConfig(
            gemini_api_key=os.getenv('GOOGLE_API_KEY', config_data['ai']['gemini_api_key'])
        )
        
        return Config(
            outlook=outlook_config,
            gmail=gmail_config,
            ai=ai_config,
            environment=env
        )
    
    def get_config(self) -> Config:
        """Get the current configuration"""
        return self.config
    
    def validate_config(self) -> Dict[str, bool]:
        """Validate the configuration"""
        outlook_valid = all([
            self.config.outlook.client_id not in ['<OUTLOOK_CLIENT_ID>', ''],
            self.config.outlook.client_secret not in ['<OUTLOOK_CLIENT_SECRET>', ''],
            self.config.outlook.tenant_id not in ['<OUTLOOK_TENANT_ID>', ''],
            self.config.outlook.email not in ['<OUTLOOK_EMAIL>', '']
        ])
        
        gmail_valid = all([
            self.config.gmail.email not in ['<GMAIL_EMAIL>', ''],
            self.config.gmail.credentials_file not in ['<CREDENTIALS_FILE_PATH>', ''],
            self.config.gmail.user_email not in ['<USER_EMAIL>', '']
        ])

        ai_valid = self.config.ai.gemini_api_key not in ['<GEMINI_API_KEY>', '']
        
        return {
            'outlook_configured': outlook_valid,
            'gmail_configured': gmail_valid,
            'ai_configured': ai_valid
        }

# Create a singleton instance
config_manager = ConfigurationManager()