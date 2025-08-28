"""
Save to Sheet Node - Saves approved posts to Google Sheets for scheduling.
"""

from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import sys
sys.path.append('..')
from state import WorkflowState
from credentials_loader import get_google_sheets_config


def save_post_to_sheet(state: WorkflowState) -> WorkflowState:
    """
    Saves the approved post to Google Sheets with scheduling information.
    
    Args:
        state: Current workflow state with final post
        
    Returns:
        Updated state with save confirmation
    """
    print("\n" + "-"*40)
    print("💾 Saving to Google Sheets")
    print("-"*40)
    
    try:
        # Check for errors or cancellation
        if state.get('error'):
            return state
        
        # Check if post is approved
        if not state.get('post_approved'):
            print("⚠️ Post not approved. Skipping save.")
            return state
        
        # Load credentials using credentials_loader
        sheets_config = get_google_sheets_config()
        service_account_file = sheets_config.get('service_account_file')
        spreadsheet_id = sheets_config.get('spreadsheet_id')
        sheet_name = sheets_config.get('sheet_name', 'Posts')
        
        # Initialize Google Sheets service
        print("🔐 Authenticating with Google Sheets...")
        creds = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Get the current data to determine post_number
        range_name = f"{sheet_name}!A:E"
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])
            
            # Calculate next post number
            if len(values) > 1:  # Skip header row
                # Get the last post number
                last_row = values[-1]
                if last_row and len(last_row) > 0 and last_row[0].isdigit():
                    post_number = int(last_row[0]) + 1
                else:
                    post_number = len(values)  # Fallback to row count
            else:
                post_number = 1
                
        except HttpError:
            # If sheet is empty or doesn't exist, start with 1
            post_number = 1
        
        print(f"📝 Assigning post number: {post_number}")
        
        # Prepare the row data
        # Format: [post_number, post, attachments, to_be_posted_at, posted_at]
        attachments = ""
        if state.get('media_paths'):
            attachments = ", ".join(state['media_paths'])
        
        scheduled_time = state.get('scheduled_time', datetime.now().strftime("%Y-%m-%d %H:%M"))
        
        row_data = [
            [
                str(post_number),
                state['final_post'],
                attachments,
                scheduled_time,
                ""  # posted_at will be filled by background.py
            ]
        ]
        
        # Append to sheet
        print("📤 Writing to Google Sheet...")
        body = {'values': row_data}
        
        append_result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:E",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        # Update state
        state['post_number'] = post_number
        state['saved_to_sheet'] = True
        
        print("\n✅ Post saved successfully!")
        print(f"   • Post Number: {post_number}")
        print(f"   • Scheduled for: {scheduled_time}")
        print(f"   • Attachments: {len(state.get('media_paths', [])) if state.get('media_paths') else 0}")
        print(f"   • Sheet: {sheet_name}")
        print(f"   • Spreadsheet ID: {spreadsheet_id[:20]}...")
        
        # Generate sheet URL
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        print(f"\n📊 View in Google Sheets:")
        print(f"   {sheet_url}")
        
        return state
        
    except FileNotFoundError as e:
        state['error'] = f"Credentials file not found: {str(e)}"
        state['error_node'] = "save_to_sheet"
        print(f"❌ Error: {str(e)}")
        return state
    except HttpError as e:
        state['error'] = f"Google Sheets API error: {str(e)}"
        state['error_node'] = "save_to_sheet"
        print(f"❌ Error: {str(e)}")
        return state
    except Exception as e:
        state['error'] = f"Error saving to sheet: {str(e)}"
        state['error_node'] = "save_to_sheet"
        print(f"❌ Error: {str(e)}")
        return state
