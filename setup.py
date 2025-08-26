"""
Automatic LinkedIn Poster - Setup Module
One-time configuration setup for the LinkedIn posting system.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class LinkedInSetup:
    """Handles LinkedIn API configuration and authentication."""
    
    @staticmethod
    def get_person_urn(access_token: str) -> Optional[str]:
        """
        Fetch the LinkedIn person URN using the access token.
        
        Args:
            access_token: LinkedIn OAuth2 access token
            
        Returns:
            Person URN string or None if failed
        """
        url = "https://api.linkedin.com/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            person_id = data.get("sub")
            if not person_id:
                print("❌ Unable to retrieve person ID from LinkedIn API response")
                return None
            return f"urn:li:person:{person_id}"
        except requests.exceptions.RequestException as e:
            print(f"❌ LinkedIn API request failed: {e}")
            return None
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            print(f"❌ Error parsing LinkedIn API response: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error fetching person_urn: {e}")
            return None


class GoogleSheetsSetup:
    """Handles Google Sheets API configuration and sheet creation."""
    
    def __init__(self, service_account_file: str):
        """
        Initialize Google Sheets service.
        
        Args:
            service_account_file: Path to service account JSON file
        """
        self.service_account_file = service_account_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using service account."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=credentials)
        except FileNotFoundError:
            raise Exception(f"Service account file not found: {self.service_account_file}")
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON in service account file: {self.service_account_file}")
        except Exception as e:
            raise Exception(f"Failed to authenticate with Google Sheets: {e}")
    
    def setup_sheet(self, spreadsheet_id: str, sheet_name: str) -> bool:
        """
        Create or verify the sheet structure with required columns.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet to create/verify
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if sheet exists
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            sheets = sheet_metadata.get('sheets', [])
            sheet_exists = any(
                s['properties']['title'] == sheet_name for s in sheets
            )
            
            if not sheet_exists:
                # Create new sheet
                request_body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': sheet_name
                            }
                        }
                    }]
                }
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=request_body
                ).execute()
                print(f"✅ Created new sheet: {sheet_name}")
            else:
                print(f"✅ Sheet '{sheet_name}' already exists")
            
            # Add headers if sheet is empty
            range_name = f"{sheet_name}!A1:E1"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                headers = [['post_number', 'post', 'attachments', 'to_be_posted_at', 'posted_at']]
                body = {'values': headers}
                self.service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                print("✅ Added column headers to sheet")
            else:
                print("✅ Sheet headers already configured")
            
            return True
            
        except HttpError as e:
            print(f"❌ Google Sheets API error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error setting up sheet: {e}")
            return False


class ConfigurationManager:
    """Manages the creation and validation of configuration files."""
    
    @staticmethod
    def validate_file_path(file_path: str, file_type: str) -> bool:
        """
        Validate if a file exists and is readable.
        
        Args:
            file_path: Path to the file
            file_type: Description of file type for error messages
            
        Returns:
            True if file is valid, False otherwise
        """
        path = Path(file_path)
        if not path.exists():
            print(f"❌ {file_type} not found: {file_path}")
            return False
        if not path.is_file():
            print(f"❌ {file_type} is not a file: {file_path}")
            return False
        if not os.access(path, os.R_OK):
            print(f"❌ {file_type} is not readable: {file_path}")
            return False
        return True
    
    @staticmethod
    def save_credentials(config: Dict[str, Any]) -> bool:
        """
        Save configuration to credentials.json file in user_info folder.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create user_info directory if it doesn't exist
            user_info_dir = Path('user_info')
            user_info_dir.mkdir(exist_ok=True)
            
            # Save credentials in user_info folder
            credentials_path = user_info_dir / 'credentials.json'
            with open(credentials_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            print(f"✅ Configuration saved to {credentials_path}")
            return True
        except Exception as e:
            print(f"❌ Error saving credentials: {e}")
            return False


def main():
    """Main setup workflow."""
    print("\n" + "="*60)
    print("AUTOMATIC LINKEDIN POSTER - SETUP")
    print("="*60)
    print("\nThis setup will configure your LinkedIn posting system.")
    print("Please have the following ready:")
    print("  1. LinkedIn Access Token")
    print("  2. Google Sheets Spreadsheet ID")
    print("  3. Service Account JSON file")
    print("  4. Persona JSON file")
    print("-"*60 + "\n")
    
    config = {}
    
    # Step 1: LinkedIn Configuration
    print("STEP 1: LinkedIn Configuration")
    print("-"*30)
    
    access_token = input("Enter your LinkedIn Access Token: ").strip()
    if not access_token:
        print("❌ Access token cannot be empty")
        sys.exit(1)
    
    print("\nValidating LinkedIn access token...")
    person_urn = LinkedInSetup.get_person_urn(access_token)
    
    if not person_urn:
        print("❌ Failed to validate LinkedIn access token")
        print("Please ensure your token is valid and has the required permissions.")
        sys.exit(1)
    
    config['linkedin_access_token'] = access_token
    config['person_urn'] = person_urn
    print(f"✅ LinkedIn authentication successful")
    print(f"   Person URN: {person_urn}\n")
    
    # Step 2: Google Sheets Configuration
    print("STEP 2: Google Sheets Configuration")
    print("-"*30)
    
    spreadsheet_id = input("Enter Google Sheets Spreadsheet ID: ").strip()
    if not spreadsheet_id:
        print("❌ Spreadsheet ID cannot be empty")
        sys.exit(1)
    
    sheet_name = input("Enter Sheet Name (default: 'Posts'): ").strip()
    if not sheet_name:
        sheet_name = "Posts"
    print(f"Using sheet name: {sheet_name}")
    
    service_account_file = input("Enter path to Service Account JSON file: ").strip()
    if not service_account_file:
        print("❌ Service account file path cannot be empty")
        sys.exit(1)
    
    # Validate service account file
    if not ConfigurationManager.validate_file_path(service_account_file, "Service Account file"):
        sys.exit(1)
    
    # Setup Google Sheets
    print("\nConfiguring Google Sheets...")
    try:
        sheets_setup = GoogleSheetsSetup(service_account_file)
        if not sheets_setup.setup_sheet(spreadsheet_id, sheet_name):
            print("❌ Failed to setup Google Sheets")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Google Sheets setup failed: {e}")
        sys.exit(1)
    
    config['google_sheets'] = {
        'spreadsheet_id': spreadsheet_id,
        'sheet_name': sheet_name,
        'service_account_file': os.path.abspath(service_account_file)
    }
    
    # Step 3: Persona Configuration
    print("\nSTEP 3: Persona Configuration")
    print("-"*30)
    
    persona_path = input("Enter path to persona.json file: ").strip()
    if not persona_path:
        print("❌ Persona file path cannot be empty")
        sys.exit(1)
    
    # Validate persona file
    if not ConfigurationManager.validate_file_path(persona_path, "Persona file"):
        sys.exit(1)
    
    # Validate persona.json structure
    try:
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona_data = json.load(f)
        print("✅ Persona file is valid JSON")
        
        # Optional: Check for expected fields
        expected_fields = ['name', 'background', 'tone', 'skills']
        missing_fields = [field for field in expected_fields if field not in persona_data]
        if missing_fields:
            print(f"⚠️  Warning: Persona file is missing recommended fields: {', '.join(missing_fields)}")
            print("   The system will still work, but posts may be less personalized.")
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in persona file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading persona file: {e}")
        sys.exit(1)
    
    config['persona_path'] = os.path.abspath(persona_path)
    
    # Step 4: Save Configuration
    print("\nSTEP 4: Saving Configuration")
    print("-"*30)
    
    if ConfigurationManager.save_credentials(config):
        print("\n" + "="*60)
        print("✅ SETUP COMPLETE!")
        print("="*60)
        print("\nYour LinkedIn posting system is now configured.")
        print("\nConfiguration summary:")
        print(f"  • LinkedIn Person URN: {person_urn}")
        print(f"  • Google Sheet: {spreadsheet_id}")
        print(f"  • Sheet Name: {sheet_name}")
        print(f"  • Service Account: {os.path.basename(service_account_file)}")
        print(f"  • Persona File: {os.path.basename(persona_path)}")
        print("\nNext steps:")
        print("  1. Run 'python main.py' to create and schedule posts")
        print("  2. Run 'python background.py' to start the auto-posting service")
        print("\n" + "="*60)
    else:
        print("❌ Setup failed. Please check the errors above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
