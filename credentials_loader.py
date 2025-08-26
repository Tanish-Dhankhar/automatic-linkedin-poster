"""
Credentials Loader Utility

This module provides utility functions to load credentials and file paths
from the credentials.json file, ensuring consistent access across all modules.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def load_credentials(credentials_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load credentials from credentials.json file.
    
    Args:
        credentials_path: Optional custom path to credentials file.
                         If not provided, looks for 'credentials.json' in current directory
                         and then in 'user_info/credentials.json'
    
    Returns:
        Dictionary containing all credentials
        
    Raises:
        FileNotFoundError: If credentials file is not found
        json.JSONDecodeError: If credentials file contains invalid JSON
    """
    if credentials_path:
        creds_path = Path(credentials_path)
    else:
        # Try current directory first, then user_info directory
        creds_path = Path('credentials.json')
        if not creds_path.exists():
            creds_path = Path('user_info/credentials.json')
    
    if not creds_path.exists():
        raise FileNotFoundError(f"Credentials file not found at: {creds_path}")
    
    with open(creds_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_service_account_file_path(credentials_path: Optional[str] = None) -> str:
    """
    Get the service account file path from credentials.json.
    
    Args:
        credentials_path: Optional custom path to credentials file
        
    Returns:
        Path to the service account JSON file
        
    Raises:
        FileNotFoundError: If credentials file is not found
        KeyError: If service account file path is not in credentials
        json.JSONDecodeError: If credentials file contains invalid JSON
    """
    credentials = load_credentials(credentials_path)
    
    google_sheets = credentials.get('google_sheets', {})
    service_account_file = google_sheets.get('service_account_file')
    
    if not service_account_file:
        raise KeyError("'service_account_file' not found in credentials.json under 'google_sheets'")
    
    return service_account_file


def get_persona_path(credentials_path: Optional[str] = None) -> str:
    """
    Get the persona file path from credentials.json.
    
    Args:
        credentials_path: Optional custom path to credentials file
        
    Returns:
        Path to the persona JSON file
        
    Raises:
        FileNotFoundError: If credentials file is not found
        KeyError: If persona path is not in credentials
        json.JSONDecodeError: If credentials file contains invalid JSON
    """
    credentials = load_credentials(credentials_path)
    
    persona_path = credentials.get('persona_path')
    
    if not persona_path:
        raise KeyError("'persona_path' not found in credentials.json")
    
    return persona_path


def get_google_sheets_config(credentials_path: Optional[str] = None) -> Dict[str, str]:
    """
    Get the complete Google Sheets configuration from credentials.json.
    
    Args:
        credentials_path: Optional custom path to credentials file
        
    Returns:
        Dictionary containing Google Sheets configuration
        
    Raises:
        FileNotFoundError: If credentials file is not found
        KeyError: If Google Sheets config is not in credentials
        json.JSONDecodeError: If credentials file contains invalid JSON
    """
    credentials = load_credentials(credentials_path)
    
    google_sheets = credentials.get('google_sheets')
    
    if not google_sheets:
        raise KeyError("'google_sheets' configuration not found in credentials.json")
    
    return google_sheets


def get_linkedin_config(credentials_path: Optional[str] = None) -> Dict[str, str]:
    """
    Get the LinkedIn configuration from credentials.json.
    
    Args:
        credentials_path: Optional custom path to credentials file
        
    Returns:
        Dictionary containing LinkedIn access token and person URN
        
    Raises:
        FileNotFoundError: If credentials file is not found
        KeyError: If LinkedIn config is incomplete
        json.JSONDecodeError: If credentials file contains invalid JSON
    """
    credentials = load_credentials(credentials_path)
    
    linkedin_token = credentials.get('linkedin_access_token')
    person_urn = credentials.get('person_urn')
    
    if not linkedin_token:
        raise KeyError("'linkedin_access_token' not found in credentials.json")
    
    if not person_urn:
        raise KeyError("'person_urn' not found in credentials.json")
    
    return {
        'linkedin_access_token': linkedin_token,
        'person_urn': person_urn
    }


def get_credentials_aware_sheets_setup():
    """
    Create a GoogleSheetsSetup instance using credentials from credentials.json.
    This is a helper for modules that need to use GoogleSheetsSetup but want
    to get the service account file path from credentials.json.
    
    Returns:
        GoogleSheetsSetup instance configured with service account from credentials.json
        
    Raises:
        ImportError: If GoogleSheetsSetup cannot be imported
        FileNotFoundError: If credentials file is not found
        KeyError: If required credentials are missing
    """
    try:
        from setup import GoogleSheetsSetup
    except ImportError:
        try:
            from setup_gradio import GoogleSheetsSetup
        except ImportError:
            raise ImportError("Could not import GoogleSheetsSetup from setup modules")
    
    service_account_file = get_service_account_file_path()
    return GoogleSheetsSetup(service_account_file)
