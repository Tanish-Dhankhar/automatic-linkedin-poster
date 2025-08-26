"""
Automatic LinkedIn Poster - Gradio Setup Interface
Modern web-based configuration setup for the LinkedIn posting system.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import gradio as gr
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class LinkedInSetup:
    """Handles LinkedIn API configuration and authentication."""
    
    @staticmethod
    def get_person_urn(access_token: str) -> Tuple[bool, str, Optional[str]]:
        """
        Fetch the LinkedIn person URN using the access token.
        
        Returns:
            Tuple of (success, message, person_urn)
        """
        url = "https://api.linkedin.com/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            person_id = data.get("sub")
            if not person_id:
                return False, "❌ Unable to retrieve person ID from LinkedIn API response", None
            person_urn = f"urn:li:person:{person_id}"
            return True, f"✅ LinkedIn authentication successful! Person URN: {person_urn}", person_urn
        except requests.exceptions.RequestException as e:
            return False, f"❌ LinkedIn API request failed: {e}", None
        except Exception as e:
            return False, f"❌ Unexpected error: {e}", None


class GoogleSheetsSetup:
    """Handles Google Sheets API configuration and sheet creation."""
    
    def __init__(self, service_account_file: str):
        """Initialize Google Sheets service."""
        self.service_account_file = service_account_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using service account."""
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=credentials)
    
    def setup_sheet(self, spreadsheet_id: str, sheet_name: str) -> Tuple[bool, str]:
        """
        Create or verify the sheet structure with required columns.
        
        Returns:
            Tuple of (success, message)
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
            
            message = ""
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
                message = f"✅ Created new sheet: {sheet_name}\n"
            else:
                message = f"✅ Sheet '{sheet_name}' already exists\n"
            
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
                message += "✅ Added column headers to sheet"
            else:
                message += "✅ Sheet headers already configured"
            
            return True, message
            
        except HttpError as e:
            return False, f"❌ Google Sheets API error: {e}"
        except Exception as e:
            return False, f"❌ Error setting up sheet: {e}"


# Global variables to store configuration
config_data = {}
temp_files = {}

def validate_linkedin_token(access_token: str) -> str:
    """Validate LinkedIn access token and return status message."""
    if not access_token.strip():
        return "⚠️ Please enter your LinkedIn Access Token"
    
    success, message, person_urn = LinkedInSetup.get_person_urn(access_token.strip())
    if success:
        config_data['linkedin_access_token'] = access_token.strip()
        config_data['person_urn'] = person_urn
    return message


def validate_google_sheets(spreadsheet_id: str, sheet_name: str, service_account_file) -> str:
    """Validate Google Sheets configuration."""
    if not spreadsheet_id.strip():
        return "⚠️ Please enter the Google Sheets Spreadsheet ID"
    
    if not sheet_name.strip():
        sheet_name = "Posts"
    
    if service_account_file is None:
        return "⚠️ Please upload your Service Account JSON file"
    
    try:
        # Save the uploaded service account file temporarily
        temp_path = Path('temp_service_account.json')
        
        # Handle both file path string and file object
        if hasattr(service_account_file, 'name'):
            # It's a file object from Gradio
            shutil.copy(service_account_file.name, temp_path)
        else:
            # It's already a path
            shutil.copy(service_account_file, temp_path)
        
        # Validate the JSON structure
        with open(temp_path, 'r') as f:
            service_data = json.load(f)
            if 'type' not in service_data or service_data['type'] != 'service_account':
                return "❌ Invalid service account file. Please ensure it's a valid Google Cloud service account JSON."
        
        # Test Google Sheets connection
        sheets_setup = GoogleSheetsSetup(str(temp_path))
        success, message = sheets_setup.setup_sheet(spreadsheet_id.strip(), sheet_name.strip())
        
        if success:
            config_data['google_sheets'] = {
                'spreadsheet_id': spreadsheet_id.strip(),
                'sheet_name': sheet_name.strip()
            }
            temp_files['service_account'] = temp_path
            return f"✅ Google Sheets configured successfully!\n{message}"
        else:
            return message
            
    except json.JSONDecodeError:
        return "❌ Invalid JSON in service account file"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def validate_persona(persona_file) -> str:
    """Validate persona JSON file."""
    if persona_file is None:
        return "⚠️ Please upload your persona.json file"
    
    try:
        # Handle both file path string and file object
        if hasattr(persona_file, 'name'):
            # It's a file object from Gradio
            with open(persona_file.name, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            temp_path = Path(persona_file.name)
        else:
            # It's already a path
            with open(persona_file, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            temp_path = Path(persona_file)
        
        # Check for recommended fields
        expected_fields = ['name', 'background', 'tone', 'skills']
        missing_fields = [field for field in expected_fields if field not in persona_data]
        
        message = "✅ Persona file is valid JSON\n"
        if missing_fields:
            message += f"⚠️ Warning: Missing recommended fields: {', '.join(missing_fields)}\n"
            message += "The system will still work, but posts may be less personalized."
        else:
            message += "✅ All recommended fields are present"
        
        temp_files['persona'] = temp_path
        return message
        
    except json.JSONDecodeError as e:
        return f"❌ Invalid JSON in persona file: {e}"
    except Exception as e:
        return f"❌ Error reading persona file: {e}"


def save_configuration() -> str:
    """Save all configuration to the user_info folder."""
    try:
        # Check if all required data is present
        if 'linkedin_access_token' not in config_data:
            return "❌ LinkedIn token not validated. Please complete Step 1."
        
        if 'google_sheets' not in config_data:
            return "❌ Google Sheets not configured. Please complete Step 2."
        
        if 'persona' not in temp_files:
            return "❌ Persona file not uploaded. Please complete Step 3."
        
        # Create user_info directory
        user_info_dir = Path('user_info')
        user_info_dir.mkdir(exist_ok=True)
        
        # Copy service account file to user_info
        service_account_dest = user_info_dir / 'service_account.json'
        shutil.copy(temp_files['service_account'], service_account_dest)
        config_data['google_sheets']['service_account_file'] = str(service_account_dest.absolute())
        
        # Copy persona file to user_info
        persona_dest = user_info_dir / 'persona.json'
        shutil.copy(temp_files['persona'], persona_dest)
        config_data['persona_path'] = str(persona_dest.absolute())
        
        # Save credentials.json
        credentials_path = user_info_dir / 'credentials.json'
        with open(credentials_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        # Clean up temp files
        for temp_file in temp_files.values():
            if temp_file.exists() and temp_file != temp_files.get('persona'):
                temp_file.unlink()
        
        if Path('temp_service_account.json').exists():
            Path('temp_service_account.json').unlink()
        
        success_message = f"""
✅ **SETUP COMPLETE!**

Your LinkedIn posting system is now configured successfully!

**Configuration Summary:**
- ✅ LinkedIn Person URN: {config_data['person_urn']}
- ✅ Google Sheet ID: {config_data['google_sheets']['spreadsheet_id']}
- ✅ Sheet Name: {config_data['google_sheets']['sheet_name']}
- ✅ Files saved in: user_info/

**Next Steps:**
1. Run `python main.py` to create and schedule posts
2. Run `python backgrounds.py` to start the auto-posting service

**Google Sheets URL:**
https://docs.google.com/spreadsheets/d/{config_data['google_sheets']['spreadsheet_id']}
"""
        return success_message
        
    except Exception as e:
        return f"❌ Error saving configuration: {str(e)}"


def create_gradio_interface():
    """Create the Gradio interface for setup."""
    
    with gr.Blocks(title="LinkedIn Auto-Poster Setup", theme=gr.themes.Soft()) as app:
        # Header
        gr.Markdown(
            """
            # 🚀 Automatic LinkedIn Poster - Setup
            ### Configure your LinkedIn posting system in 3 easy steps
            """
        )
        
        with gr.Tabs():
            # Step 1: LinkedIn Configuration
            with gr.TabItem("Step 1: LinkedIn", id=1):
                gr.Markdown(
                    """
                    ## LinkedIn Configuration
                    Enter your LinkedIn Access Token to authenticate with the LinkedIn API.
                    
                    **How to get your access token:**
                    1. Visit [LinkedIn Developer Portal](https://www.linkedin.com/developers/)
                    2. Create an app or use existing one
                    3. Generate an access token with `w_member_social` permission
                    """
                )
                
                with gr.Row():
                    with gr.Column():
                        linkedin_token = gr.Textbox(
                            label="LinkedIn Access Token",
                            placeholder="Enter your LinkedIn access token here...",
                            type="password",
                            lines=2
                        )
                        validate_linkedin_btn = gr.Button("Validate Token", variant="primary")
                    
                    with gr.Column():
                        linkedin_status = gr.Textbox(
                            label="Validation Status",
                            lines=3,
                            interactive=False
                        )
                
                validate_linkedin_btn.click(
                    validate_linkedin_token,
                    inputs=[linkedin_token],
                    outputs=[linkedin_status]
                )
            
            # Step 2: Google Sheets Configuration
            with gr.TabItem("Step 2: Google Sheets", id=2):
                gr.Markdown(
                    """
                    ## Google Sheets Configuration
                    Set up Google Sheets to store your scheduled posts.
                    
                    **Requirements:**
                    1. A Google Sheets spreadsheet (create one or use existing)
                    2. Service Account JSON file from Google Cloud Console
                    3. Share the spreadsheet with the service account email
                    """
                )
                
                with gr.Row():
                    with gr.Column():
                        spreadsheet_id = gr.Textbox(
                            label="Spreadsheet ID",
                            placeholder="e.g., 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                            info="Found in the spreadsheet URL after /d/"
                        )
                        sheet_name = gr.Textbox(
                            label="Sheet Name",
                            placeholder="Posts",
                            value="Posts",
                            info="Name of the sheet tab (default: Posts)"
                        )
                        service_account_file = gr.File(
                            label="Service Account JSON File",
                            file_types=[".json"],
                            type="filepath"
                        )
                        validate_sheets_btn = gr.Button("Validate Configuration", variant="primary")
                    
                    with gr.Column():
                        sheets_status = gr.Textbox(
                            label="Validation Status",
                            lines=5,
                            interactive=False
                        )
                
                validate_sheets_btn.click(
                    validate_google_sheets,
                    inputs=[spreadsheet_id, sheet_name, service_account_file],
                    outputs=[sheets_status]
                )
            
            # Step 3: Persona Configuration
            with gr.TabItem("Step 3: Persona", id=3):
                gr.Markdown(
                    """
                    ## Persona Configuration
                    Upload your persona.json file that contains your professional profile information.
                    
                    **Recommended fields in persona.json:**
                    - `name`: Your full name
                    - `background`: Your professional background
                    - `tone`: Your preferred writing tone
                    - `skills`: Your skills and expertise
                    """
                )
                
                with gr.Row():
                    with gr.Column():
                        persona_file = gr.File(
                            label="Persona JSON File",
                            file_types=[".json"],
                            type="filepath"
                        )
                        
                        gr.Markdown(
                            """
                            **Sample persona.json structure:**
                            ```json
                            {
                                "name": "John Doe",
                                "background": "Software Engineer with 5 years experience",
                                "tone": "Professional yet approachable",
                                "skills": ["Python", "Machine Learning", "Cloud Computing"]
                            }
                            ```
                            """
                        )
                        
                        validate_persona_btn = gr.Button("Validate Persona", variant="primary")
                    
                    with gr.Column():
                        persona_status = gr.Textbox(
                            label="Validation Status",
                            lines=5,
                            interactive=False
                        )
                
                validate_persona_btn.click(
                    validate_persona,
                    inputs=[persona_file],
                    outputs=[persona_status]
                )
            
            # Final Step: Save Configuration
            with gr.TabItem("Finalize Setup", id=4):
                gr.Markdown(
                    """
                    ## Finalize Configuration
                    Review your setup and save the configuration.
                    
                    **Before saving:**
                    - ✅ Ensure LinkedIn token is validated
                    - ✅ Ensure Google Sheets is configured
                    - ✅ Ensure Persona file is uploaded
                    
                    Click the button below to save all configurations.
                    """
                )
                
                with gr.Row():
                    with gr.Column(scale=1):
                        save_btn = gr.Button(
                            "💾 Save Configuration",
                            variant="primary",
                            size="lg"
                        )
                    
                with gr.Row():
                    final_status = gr.Markdown()
                
                save_btn.click(
                    save_configuration,
                    outputs=[final_status]
                )
        
        # Footer
        gr.Markdown(
            """
            ---
            ### Need Help?
            - 📖 Check the documentation for detailed setup instructions
            - 🐛 Report issues on the project repository
            - 💡 Make sure to keep your credentials secure and never share them
            """
        )
    
    return app


def main():
    """Main entry point for the Gradio setup interface."""
    print("\n" + "="*60)
    print("🚀 AUTOMATIC LINKEDIN POSTER - SETUP")
    print("="*60)
    print("\nLaunching web interface...")
    print("Open your browser and navigate to the URL shown below.\n")
    
    # Create and launch the Gradio app
    app = create_gradio_interface()
    app.launch(
        share=False,
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        show_api=False
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
