"""
Automatic LinkedIn Poster - Complete Gradio Web Interface
A comprehensive web UI for the LinkedIn posting system with all features.
"""

import gradio as gr
import json
import os
import sys
import traceback
import pandas as pd
import subprocess
import time
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

# Add current directory to path for imports
sys.path.append('.')

# Import our modules
try:
    from credentials_loader import load_credentials, get_google_sheets_config, get_linkedin_config, get_persona_path
    from setup import LinkedInSetup, GoogleSheetsSetup, ConfigurationManager
    from background import LinkedInScheduler, GoogleSheetsManager
    
    # Import workflow components
    from state import WorkflowState
    from nodes.input_collector import collect_user_input
    from nodes.structure_input import structure_user_input
    from nodes.validate_completeness import validate_and_complete
    from nodes.enrich_persona import enrich_with_persona
    from nodes.generate_post import generate_linkedin_post
    from nodes.refine_post import refine_and_humanize_post
    from nodes.save_to_sheet import save_post_to_sheet
    from nodes.update_persona import update_persona_from_post
except ImportError as e:
    print(f"Warning: Some modules not available: {e}")

# Global variables
background_scheduler = None
scheduler_thread = None
scheduler_running = False

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


class GradioWorkflowAdapter:
    """Adapts the CLI workflow for Gradio interface."""
    
    def __init__(self):
        self.state = None
        self.workflow_steps = []
        
    def create_post_from_input(self, content: str, attachments: List[str], scheduled_time: str, progress=None) -> Dict[str, Any]:
        """
        Create a LinkedIn post from user input using the workflow.
        
        Args:
            content: Raw post content
            attachments: List of attachment file paths
            scheduled_time: When to schedule the post
            progress: Gradio progress indicator
            
        Returns:
            Dictionary with results and status
        """
        try:
            # Initialize state
            self.state = WorkflowState()
            
            # Mark that we're running in Gradio mode
            self.state['gradio_mode'] = True
            
            if progress:
                progress(0.1, "Loading persona and credentials...")
            
            # Load persona data
            try:
                persona_path = get_persona_path()
                with open(persona_path, 'r', encoding='utf-8') as f:
                    persona_data = json.load(f)
                
                self.state['persona_data'] = persona_data
                self.state['raw_input'] = content
                self.state['media_paths'] = attachments if attachments else None
                self.state['scheduled_time'] = scheduled_time if scheduled_time else datetime.now().strftime("%Y-%m-%d %H:%M")
                self.state['revision_count'] = 0
                
            except Exception as e:
                return {"success": False, "error": f"Failed to load persona: {str(e)}"}
            
            if progress:
                progress(0.2, "Structuring input...")
            
            # Step 1: Structure input
            self.state = structure_user_input(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(0.3, "Validating completeness...")
            
            # Step 2: Validate completeness
            self.state = validate_and_complete(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            # If incomplete, return clarification request
            if not self.state.get('is_complete', True):
                return {
                    "success": False,
                    "needs_clarification": True,
                    "questions": self.state.get('clarifying_questions', []),
                    "missing_fields": self.state.get('missing_fields', []),
                    "state": self.state  # Keep the state for continuation
                }
            
            if progress:
                progress(0.5, "Enriching with persona context...")
            
            # Step 3: Enrich with persona
            self.state = enrich_with_persona(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(0.6, "Generating LinkedIn post...")
            
            # Step 4: Generate post
            self.state = generate_linkedin_post(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(0.8, "Refining and humanizing...")
            
            # Step 5: Refine post
            self.state = refine_and_humanize_post(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(1.0, "Complete!")
            
            # Prepare result
            result = {
                "success": True,
                "draft_post": self.state.get('draft_post', ''),
                "refined_post": self.state.get('refined_post', ''),
                "post_metadata": self.state.get('post_metadata', {}),
                "event_details": self.state.get('event_details', {}),
                "persona_context": self.state.get('persona_context', {}),
                "state": self.state
            }
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"Workflow error: {str(e)}"}
    
    def continue_with_clarification(self, answers: Dict[str, str], progress=None) -> Dict[str, Any]:
        """
        Continue workflow after user provides clarification answers.
        
        Args:
            answers: Dictionary with question numbers as keys and user answers as values
            progress: Gradio progress indicator
            
        Returns:
            Dictionary with results and status
        """
        try:
            if not self.state:
                return {"success": False, "error": "No workflow state available"}
            
            if progress:
                progress(0.1, "Processing clarification answers...")
            
            # Add answers to state
            self.state['clarification_answers'] = answers
            
            # Re-run validation with the new information
            if progress:
                progress(0.2, "Re-validating completeness...")
            
            # Import function to update structured data with answers
            from nodes.validate_completeness import integrate_clarification_answers
            self.state = integrate_clarification_answers(self.state)
            
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            # Continue with the rest of the workflow
            if progress:
                progress(0.4, "Enriching with persona context...")
            
            # Step 3: Enrich with persona
            self.state = enrich_with_persona(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(0.6, "Generating LinkedIn post...")
            
            # Step 4: Generate post
            self.state = generate_linkedin_post(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(0.8, "Refining and humanizing...")
            
            # Step 5: Refine post
            self.state = refine_and_humanize_post(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(1.0, "Complete!")
            
            # Prepare result
            result = {
                "success": True,
                "draft_post": self.state.get('draft_post', ''),
                "refined_post": self.state.get('refined_post', ''),
                "post_metadata": self.state.get('post_metadata', {}),
                "event_details": self.state.get('event_details', {}),
                "persona_context": self.state.get('persona_context', {}),
                "state": self.state
            }
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"Clarification workflow error: {str(e)}"}
    
    def approve_and_save_post(self, post_content: str) -> Dict[str, Any]:
        """Approve post and save to Google Sheets."""
        try:
            if not self.state:
                return {"success": False, "error": "No workflow state available"}
            
            # Set approved post
            self.state['post_approved'] = True
            self.state['final_post'] = post_content
            
            # Save to sheet
            self.state = save_post_to_sheet(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            # Update persona
            self.state = update_persona_from_post(self.state)
            
            return {
                "success": True,
                "post_number": self.state.get('post_number'),
                "scheduled_time": self.state.get('scheduled_time'),
                "persona_updated": self.state.get('persona_updated', False),
                "saved_to_sheet": self.state.get('saved_to_sheet', False)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Save error: {str(e)}"}
    
    def revise_post(self, post_content: str, feedback: str, progress=None) -> Dict[str, Any]:
        """Revise the post based on user feedback."""
        try:
            if not self.state:
                return {"success": False, "error": "No workflow state available"}
            
            if progress:
                progress(0.1, "Processing revision request...")
            
            # Import the revision function from user_approval node
            from nodes.user_approval import revise_post
            
            # Update state with current content and feedback
            self.state['draft_post'] = post_content
            self.state['user_feedback'] = feedback
            self.state['revision_count'] = self.state.get('revision_count', 0) + 1
            
            if progress:
                progress(0.5, "Applying revisions with AI...")
            
            # Use the revise_post function
            self.state = revise_post(self.state, feedback)
            
            if progress:
                progress(1.0, "Revision complete!")
            
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            # Calculate stats for revised post
            revised_text = self.state.get('draft_post', '')
            word_count = len(revised_text.split())
            char_count = len(revised_text)
            
            return {
                "success": True,
                "revised_post": revised_text,
                "word_count": word_count,
                "char_count": char_count,
                "revision_count": self.state.get('revision_count', 0)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Revision error: {str(e)}"}
    
    def regenerate_post(self, progress=None) -> Dict[str, Any]:
        """Regenerate the post completely from scratch."""
        try:
            if not self.state:
                return {"success": False, "error": "No workflow state available"}
            
            if progress:
                progress(0.1, "Regenerating from original input...")
            
            # Increment revision count
            self.state['revision_count'] = self.state.get('revision_count', 0) + 1
            
            # Clear previous generated content
            self.state['draft_post'] = None
            self.state['refined_post'] = None
            
            if progress:
                progress(0.3, "Generating new post...")
            
            # Regenerate post
            self.state = generate_linkedin_post(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(0.8, "Refining new post...")
            
            # Refine the new post
            self.state = refine_and_humanize_post(self.state)
            if self.state.get('error'):
                return {"success": False, "error": self.state['error']}
            
            if progress:
                progress(1.0, "New post ready!")
            
            # Calculate stats
            new_post = self.state.get('refined_post', '')
            word_count = len(new_post.split())
            char_count = len(new_post)
            
            return {
                "success": True,
                "new_post": new_post,
                "word_count": word_count,
                "char_count": char_count,
                "revision_count": self.state.get('revision_count', 0)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Regeneration error: {str(e)}"}


class SetupManager:
    """Manages system setup through Gradio interface."""
    
    @staticmethod
    def validate_linkedin_token(access_token: str) -> Tuple[bool, str, str]:
        """Validate LinkedIn access token and get person URN."""
        if not access_token.strip():
            return False, "Access token cannot be empty", ""
        
        try:
            person_urn = LinkedInSetup.get_person_urn(access_token.strip())
            if person_urn:
                return True, "LinkedIn token validated successfully", person_urn
            else:
                return False, "Invalid LinkedIn access token", ""
        except Exception as e:
            return False, f"Error validating token: {str(e)}", ""
    
    @staticmethod
    def validate_google_sheets(spreadsheet_id: str, sheet_name: str, service_account_file: str) -> Tuple[bool, str]:
        """Validate Google Sheets configuration."""
        if not all([spreadsheet_id.strip(), sheet_name.strip(), service_account_file.strip()]):
            return False, "All Google Sheets fields are required"
        
        if not os.path.exists(service_account_file):
            return False, f"Service account file not found: {service_account_file}"
        
        try:
            sheets_setup = GoogleSheetsSetup(service_account_file)
            success = sheets_setup.setup_sheet(spreadsheet_id.strip(), sheet_name.strip())
            if success:
                return True, "Google Sheets configured successfully"
            else:
                return False, "Failed to configure Google Sheets"
        except Exception as e:
            return False, f"Google Sheets error: {str(e)}"
    
    @staticmethod
    def validate_persona_file(persona_file_path: str) -> Tuple[bool, str]:
        """Validate persona file."""
        if not persona_file_path.strip():
            return False, "Persona file path is required"
        
        if not os.path.exists(persona_file_path):
            return False, f"Persona file not found: {persona_file_path}"
        
        try:
            with open(persona_file_path, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            
            # Check for expected fields
            expected_fields = ['basic_info', 'background', 'communication_preferences']
            missing_fields = [field for field in expected_fields if field not in persona_data]
            
            if missing_fields:
                return True, f"Persona file loaded with warnings: Missing fields: {', '.join(missing_fields)}"
            else:
                return True, "Persona file validated successfully"
        except json.JSONDecodeError:
            return False, "Invalid JSON in persona file"
        except Exception as e:
            return False, f"Error reading persona file: {str(e)}"
    
    @staticmethod
    def save_configuration(linkedin_token: str, person_urn: str, spreadsheet_id: str, 
                          sheet_name: str, service_account_file: str, persona_path: str) -> Tuple[bool, str]:
        """Save complete configuration."""
        try:
            config = {
                'linkedin_access_token': linkedin_token,
                'person_urn': person_urn,
                'google_sheets': {
                    'spreadsheet_id': spreadsheet_id,
                    'sheet_name': sheet_name,
                    'service_account_file': os.path.abspath(service_account_file)
                },
                'persona_path': os.path.abspath(persona_path)
            }
            
            success = ConfigurationManager.save_credentials(config)
            if success:
                return True, "Configuration saved successfully! You can now use the Post Creator."
            else:
                return False, "Failed to save configuration"
        except Exception as e:
            return False, f"Error saving configuration: {str(e)}"


def check_system_status() -> Tuple[bool, str, Dict[str, Any]]:
    """Check if system is properly configured."""
    try:
        # Check credentials
        credentials = load_credentials()
        
        # Check required files
        persona_path = get_persona_path()
        if not os.path.exists(persona_path):
            return False, "Persona file not found", {}
        
        # Check Google Sheets config
        sheets_config = get_google_sheets_config()
        service_account_file = sheets_config.get('service_account_file')
        if not os.path.exists(service_account_file):
            return False, "Service account file not found", {}
        
        return True, "System configured correctly", {
            "linkedin_configured": bool(credentials.get('linkedin_access_token')),
            "sheets_configured": bool(sheets_config.get('spreadsheet_id')),
            "persona_configured": os.path.exists(persona_path)
        }
        
    except FileNotFoundError:
        return False, "Configuration not found. Please run setup first.", {}
    except Exception as e:
        return False, f"Configuration error: {str(e)}", {}


def get_scheduled_posts() -> pd.DataFrame:
    """Get scheduled posts from Google Sheets."""
    try:
        sheets_manager = GoogleSheetsManager()
        posts = sheets_manager.get_posts()
        
        if not posts:
            return pd.DataFrame(columns=['Post #', 'Content Preview', 'Scheduled Time', 'Posted', 'Status'])
        
        # Convert to DataFrame for display
        data = []
        for post in posts:
            content_preview = post.get('post', '')[:100] + '...' if len(post.get('post', '')) > 100 else post.get('post', '')
            status = 'Posted' if post.get('posted_at', '').strip() else 'Scheduled'
            
            data.append({
                'Post #': post.get('post_number', 'N/A'),
                'Content Preview': content_preview,
                'Scheduled Time': post.get('to_be_posted_at', 'N/A'),
                'Posted': post.get('posted_at', 'Not yet'),
                'Status': status
            })
        
        return pd.DataFrame(data)
        
    except Exception as e:
        return pd.DataFrame({'Error': [f"Failed to load posts: {str(e)}"]})


def start_background_scheduler():
    """Start the background posting scheduler."""
    global background_scheduler, scheduler_thread, scheduler_running
    
    if scheduler_running:
        return "Background scheduler is already running"
    
    try:
        background_scheduler = LinkedInScheduler()
        scheduler_running = True
        
        def run_scheduler():
            global scheduler_running
            try:
                while scheduler_running:
                    background_scheduler.check_and_post()
                    time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                print(f"Scheduler error: {e}")
            finally:
                scheduler_running = False
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        return "✅ Background scheduler started successfully!"
        
    except Exception as e:
        scheduler_running = False
        return f"❌ Failed to start scheduler: {str(e)}"


def stop_background_scheduler():
    """Stop the background posting scheduler."""
    global scheduler_running
    
    if not scheduler_running:
        return "Background scheduler is not running"
    
    scheduler_running = False
    return "✅ Background scheduler stopped"


def get_scheduler_status():
    """Get current scheduler status."""
    global scheduler_running
    
    if scheduler_running:
        return "🟢 Running", "The background scheduler is actively checking for posts to publish"
    else:
        return "🔴 Stopped", "The background scheduler is not running. Posts will not be automatically published."


# Initialize workflow adapter
workflow_adapter = GradioWorkflowAdapter()

# Create the Gradio interface
def create_interface():
    """Create the complete Gradio interface."""
    
    with gr.Blocks(title="LinkedIn Auto Poster", theme=gr.themes.Soft()) as app:
        gr.Markdown("""
        # 🚀 Automatic LinkedIn Poster
        
        **Complete AI-powered LinkedIn posting system with LangGraph workflow**
        
        Transform your ideas into engaging LinkedIn posts using advanced AI, then schedule and publish them automatically.
        """)
        
        # System status check with error handling
        try:
            system_configured, status_message, config_details = check_system_status()
        except Exception as e:
            # If status check fails, assume not configured
            system_configured = False
            status_message = f"Status check failed: {str(e)}"
            config_details = {}
        
        if not system_configured:
            gr.Warning(f"⚠️ {status_message}")
        
        with gr.Tabs() as tabs:
            
            # ============================================================
            # SETUP TAB
            # ============================================================
            with gr.Tab("🛠️ Setup", id=0):
                gr.Markdown("""
                ## Initial System Configuration
                Configure your LinkedIn API access, Google Sheets integration, and persona settings.
                """)
                
                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Group():
                            gr.Markdown("### 1. LinkedIn Configuration")
                            
                            linkedin_token = gr.Textbox(
                                label="LinkedIn Access Token",
                                placeholder="Enter your LinkedIn OAuth2 access token",
                                type="password",
                                info="Get this from LinkedIn Developer Console"
                            )
                            
                            linkedin_validate_btn = gr.Button("Validate LinkedIn Token", variant="secondary")
                            linkedin_status = gr.Textbox(label="Validation Status", interactive=False)
                            linkedin_urn = gr.Textbox(label="Person URN", interactive=False)
                        
                        with gr.Group():
                            gr.Markdown("### 2. Google Sheets Configuration")
                            
                            spreadsheet_id = gr.Textbox(
                                label="Google Sheets Spreadsheet ID",
                                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                                info="Extract from your Google Sheets URL"
                            )
                            
                            sheet_name = gr.Textbox(
                                label="Sheet Name",
                                value="Posts",
                                placeholder="Posts"
                            )
                            
                            service_account_file = gr.File(
                                label="Service Account JSON File",
                                file_types=[".json"]
                            )
                            
                            sheets_validate_btn = gr.Button("Validate Google Sheets", variant="secondary")
                            sheets_status = gr.Textbox(label="Validation Status", interactive=False)
                        
                        with gr.Group():
                            gr.Markdown("### 3. Persona Configuration")
                            
                            persona_file = gr.File(
                                label="Persona JSON File",
                                file_types=[".json"]
                            )
                            
                            persona_validate_btn = gr.Button("Validate Persona File", variant="secondary")
                            persona_status = gr.Textbox(label="Validation Status", interactive=False)
                        
                        with gr.Group():
                            gr.Markdown("### 4. Save Configuration")
                            
                            save_config_btn = gr.Button("Save Complete Configuration", variant="primary", size="lg")
                            config_status = gr.Textbox(label="Configuration Status", interactive=False)
                    
                    with gr.Column(scale=1):
                        gr.Markdown("""
                        ### Setup Instructions
                        
                        **LinkedIn Token:**
                        1. Go to [LinkedIn Developer Console](https://developer.linkedin.com/)
                        2. Create an app and get OAuth2 token
                        3. Ensure `w_member_social` permission
                        
                        **Google Sheets:**
                        1. Create a Google Sheets document
                        2. Copy the spreadsheet ID from URL
                        3. Create service account in Google Cloud
                        4. Download JSON key file
                        5. Share sheet with service account email
                        
                        **Persona File:**
                        Create a JSON file with your profile:
                        ```json
                        {
                          "basic_info": {
                            "full_name": "Your Name",
                            "role": "Your Role"
                          },
                          "communication_preferences": {
                            "tone": "professional"
                          }
                        }
                        ```
                        """)
            
            # ============================================================
            # POST CREATOR TAB
            # ============================================================
            with gr.Tab("✍️ Post Creator", id=1):
                gr.Markdown("""
                ## AI-Powered Post Creation
                Create engaging LinkedIn posts using advanced AI workflow with persona integration.
                """)
                
                if not system_configured:
                    gr.Warning("⚠️ System not configured. Please complete setup first.")
                
                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Group():
                            gr.Markdown("### Content Input")
                            
                            post_content = gr.Textbox(
                                label="Your Content",
                                placeholder="""Share what you want to post about. This can be rough notes, bullet points, or a brief description.

Examples:
- "I just completed a machine learning project that predicts..."
- "Attended an amazing conference on AI ethics..."
- "Finished my internship at XYZ company..."
                                """,
                                lines=8,
                                info="Be as detailed or as brief as you want - the AI will help structure it"
                            )
                            
                            attachments = gr.File(
                                label="Attachments (Optional)",
                                file_count="multiple",
                                file_types=["image", ".pdf", ".doc", ".docx"]
                            )
                            
                            with gr.Row():
                                scheduled_date = gr.DateTime(
                                    label="Schedule Date & Time (Optional)",
                                    info="Select when you want this post to be published. Leave empty to post immediately.",
                                    include_time=True
                                )
                        
                        with gr.Row():
                            create_post_btn = gr.Button("🚀 Create Post", variant="primary", size="lg")
                            clear_btn = gr.Button("Clear", variant="secondary")
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### AI Workflow Steps")
                        
                        workflow_status = gr.Textbox(
                            label="Current Step",
                            value="Ready to start...",
                            interactive=False
                        )
                        
                        progress_bar = gr.Progress()
                
                # Post Generation Results
                with gr.Group(visible=False) as post_results:
                    gr.Markdown("### 🎯 Generated Post")
                    
                    with gr.Tabs():
                        with gr.Tab("Draft Post"):
                            generated_post = gr.Textbox(
                                label="Generated LinkedIn Post",
                                lines=12,
                                interactive=True,
                                info="You can edit this post before approving"
                            )
                            
                            post_stats = gr.Textbox(
                                label="Post Statistics",
                                interactive=False
                            )
                        
                        with gr.Tab("Metadata"):
                            post_metadata_display = gr.JSON(
                                label="Post Metadata"
                            )
                        
                        with gr.Tab("Event Details"):
                            event_details_display = gr.JSON(
                                label="Event Details"
                            )
                    
                    with gr.Row():
                        approve_btn = gr.Button("✅ Approve & Schedule", variant="primary")
                        revise_btn = gr.Button("🔄 Revise", variant="secondary")
                        regenerate_btn = gr.Button("🎲 Regenerate", variant="secondary")
                
                # Revision feedback section (initially hidden)
                with gr.Group(visible=False) as revision_feedback_group:
                    gr.Markdown("### ✏️ Revision Request")
                    
                    revision_feedback = gr.Textbox(
                        label="What changes would you like?",
                        placeholder="""Be specific about what to add, remove, or modify.

Examples:
- "Make it more casual and add some emojis"
- "Remove the technical jargon and make it simpler"
- "Add a call-to-action at the end"
- "Make it shorter and more engaging"
- "Focus more on the business impact""",
                        lines=4,
                        info="Describe the specific changes you want to make to the post"
                    )
                    
                    with gr.Row():
                        apply_revision_btn = gr.Button("📝 Apply Revision", variant="primary")
                        cancel_revision_btn = gr.Button("❌ Cancel", variant="secondary")
                
                # Clarification Questions Section (initially hidden)
                with gr.Group(visible=False) as clarification_group:
                    gr.Markdown("""
                    ### 🤖 LLM Stage 2: Validating Completeness
                    ----------------------------------------
                    🔍 Analyzing content completeness...
                    
                    ⚠️ Additional information needed for a complete post.
                    """)
                    
                    missing_fields_display = gr.Textbox(
                        label="Missing fields",
                        interactive=False
                    )
                    
                    gr.Markdown("**Please answer these questions to enhance your post:**")
                    
                    # Questions display and answers
                    questions_display = gr.Markdown(value="", visible=False)
                    
                    answer1 = gr.Textbox(
                        label="1. Your answer:",
                        placeholder="Please provide your answer here...",
                        lines=3,
                        visible=False
                    )
                    
                    answer2 = gr.Textbox(
                        label="2. Your answer:",
                        placeholder="Please provide your answer here...",
                        lines=3,
                        visible=False
                    )
                    
                    answer3 = gr.Textbox(
                        label="3. Your answer:",
                        placeholder="Please provide your answer here...",
                        lines=3,
                        visible=False
                    )
                    
                    answer4 = gr.Textbox(
                        label="4. Your answer:",
                        placeholder="Please provide your answer here...",
                        lines=3,
                        visible=False
                    )
                    
                    answer5 = gr.Textbox(
                        label="5. Your answer:",
                        placeholder="Please provide your answer here...",
                        lines=3,
                        visible=False
                    )
                    
                    clarification_answers = [answer1, answer2, answer3, answer4, answer5]
                    
                    with gr.Row():
                        submit_answers_btn = gr.Button("📤 Submit Answers & Continue", variant="primary")
                        skip_questions_btn = gr.Button("⏭️ Skip Questions", variant="secondary")
                
                # Approval Results
                approval_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    visible=False
                )
            
            # ============================================================
            # DASHBOARD TAB
            # ============================================================
            with gr.Tab("📊 Dashboard", id=2):
                gr.Markdown("""
                ## Scheduled Posts Dashboard
                View, manage, and monitor your scheduled LinkedIn posts.
                """)
                
                if not system_configured:
                    gr.Warning("⚠️ System not configured. Please complete setup first.")
                
                with gr.Row():
                    refresh_posts_btn = gr.Button("🔄 Refresh", variant="secondary")
                    export_posts_btn = gr.Button("📥 Export", variant="secondary")
                
                # Posts table
                posts_table = gr.DataFrame(
                    label="Scheduled Posts",
                    headers=['Post #', 'Content Preview', 'Scheduled Time', 'Posted', 'Status'],
                    interactive=False
                )
                
                # Background Scheduler Control
                with gr.Group():
                    gr.Markdown("### 🤖 Background Posting Service")
                    
                    with gr.Row():
                        scheduler_status_text = gr.Textbox(
                            label="Status",
                            interactive=False
                        )
                        scheduler_info = gr.Textbox(
                            label="Information",
                            interactive=False
                        )
                    
                    with gr.Row():
                        start_scheduler_btn = gr.Button("▶️ Start Scheduler", variant="primary")
                        stop_scheduler_btn = gr.Button("⏹️ Stop Scheduler", variant="secondary")
                    
                    scheduler_message = gr.Textbox(
                        label="Scheduler Messages",
                        interactive=False
                    )
            
            # ============================================================
            # SETTINGS TAB  
            # ============================================================
            with gr.Tab("⚙️ Settings", id=3):
                gr.Markdown("""
                ## System Settings & Management
                Manage your configuration, view system status, and access advanced features.
                """)
                
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            gr.Markdown("### System Status")
                            
                            system_status = gr.Textbox(
                                label="Configuration Status",
                                value=status_message,
                                interactive=False
                            )
                            
                            check_status_btn = gr.Button("Check Status", variant="secondary")
                        
                        with gr.Group():
                            gr.Markdown("### Configuration Management")
                            
                            config_display = gr.JSON(
                                label="Current Configuration",
                                value=config_details if system_configured else {}
                            )
                            
                            backup_config_btn = gr.Button("Backup Configuration", variant="secondary")
                            restore_config_btn = gr.Button("Restore Configuration", variant="secondary")
                    
                    with gr.Column():
                        with gr.Group():
                            gr.Markdown("### System Information")
                            
                            sys_info = gr.Textbox(
                                label="System Info",
                                value=f"""
                                Python: {sys.version.split()[0]}
                                Working Directory: {os.getcwd()}
                                Gradio Version: {gr.__version__}
                                """.strip(),
                                interactive=False,
                                lines=5
                            )
                        
                        with gr.Group():
                            gr.Markdown("### Quick Actions")
                            
                            view_logs_btn = gr.Button("📋 View Logs", variant="secondary")
                            clear_cache_btn = gr.Button("🗑️ Clear Cache", variant="secondary")
                            reset_system_btn = gr.Button("⚠️ Reset System", variant="stop")
        
        # ============================================================
        # EVENT HANDLERS
        # ============================================================
        
        # Setup tab handlers
        def validate_linkedin_token_handler(token):
            success, message, urn = SetupManager.validate_linkedin_token(token)
            return message, urn if success else ""
        
        linkedin_validate_btn.click(
            validate_linkedin_token_handler,
            inputs=[linkedin_token],
            outputs=[linkedin_status, linkedin_urn]
        )
        
        def validate_google_sheets_handler(spreadsheet_id, sheet_name, service_file):
            if service_file is None:
                return "Please upload service account file"
            success, message = SetupManager.validate_google_sheets(spreadsheet_id, sheet_name, service_file.name)
            return message
        
        sheets_validate_btn.click(
            validate_google_sheets_handler,
            inputs=[spreadsheet_id, sheet_name, service_account_file],
            outputs=[sheets_status]
        )
        
        def validate_persona_handler(persona_file):
            if persona_file is None:
                return "Please upload persona file"
            success, message = SetupManager.validate_persona_file(persona_file.name)
            return message
        
        persona_validate_btn.click(
            validate_persona_handler,
            inputs=[persona_file],
            outputs=[persona_status]
        )
        
        def save_configuration_handler(token, urn, spreadsheet_id, sheet_name, service_file, persona_file):
            if None in [service_file, persona_file]:
                return "Please upload all required files"
            
            success, message = SetupManager.save_configuration(
                token, urn, spreadsheet_id, sheet_name, service_file.name, persona_file.name
            )
            return message
        
        save_config_btn.click(
            save_configuration_handler,
            inputs=[linkedin_token, linkedin_urn, spreadsheet_id, sheet_name, service_account_file, persona_file],
            outputs=[config_status]
        )
        
        # Post Creator handlers
        def create_post_handler(content, attachments, scheduled_datetime, progress=gr.Progress()):
            if not content.strip():
                # Return tuple for all outputs: post_results, clarification_group, missing_fields_display, questions_display, answer1-5, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
                return (gr.Group(visible=False), gr.Group(visible=False), "", "", "", "", "", "", "", "", "", "", {}, {}, "Please enter some content to create a post")
            
            # Process attachments
            attachment_paths = []
            if attachments:
                for file in attachments:
                    attachment_paths.append(file.name)
            
            # Convert datetime to string format if provided
            scheduled_time = None
            if scheduled_datetime:
                if isinstance(scheduled_datetime, str):
                    scheduled_time = scheduled_datetime
                else:
                    # Convert datetime object to string format
                    scheduled_time = scheduled_datetime.strftime("%Y-%m-%d %H:%M")
            
            # Run workflow
            result = workflow_adapter.create_post_from_input(content, attachment_paths, scheduled_time, progress)
            
            if not result["success"]:
                # Check if clarification is needed
                if result.get("needs_clarification"):
                    questions = result.get("questions", [])
                    missing_fields = result.get("missing_fields", [])
                    
                    # Format missing fields display
                    missing_fields_text = ", ".join(missing_fields) if missing_fields else "None specified"
                    
                    # Format questions for display
                    questions_text = "\n\n".join([f"**{i+1}. {q}**" for i, q in enumerate(questions)])
                    
                    # Create answer field values - configure visibility and labels for each question
                    answer_updates = []
                    for i in range(5):
                        if i < len(questions):
                            answer_updates.append(gr.Textbox(
                                label=f"{i+1}. {questions[i]}",
                                placeholder="Please provide your answer here...",
                                lines=3,
                                visible=True,
                                value=""  # Clear any previous values
                            ))
                        else:
                            answer_updates.append(gr.Textbox(visible=False, value=""))
                    
                    # Return tuple: post_results, clarification_group, missing_fields_display, questions_display, answer1-5, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
                    return (
                        gr.Group(visible=False),  # post_results
                        gr.Group(visible=True),   # clarification_group
                        missing_fields_text,      # missing_fields_display
                        questions_text,           # questions_display
                    ) + tuple(answer_updates) + (
                        "",  # generated_post
                        "",  # post_stats
                        {},  # post_metadata_display
                        {},  # event_details_display
                        f"\u2139\ufe0f Additional information needed. Please answer {len(questions)} questions below."  # workflow_status
                    )
                else:
                    # Regular error case
                    return (gr.Group(visible=False), gr.Group(visible=False), "", "", "", "", "", "", "", "", "", "", {}, {}, f"Error: {result.get('error', 'Unknown error')}")
            
            # Success case - post generated
            post_text = result["refined_post"]
            word_count = len(post_text.split())
            char_count = len(post_text)
            stats_text = f"Words: {word_count} | Characters: {char_count} | Lines: {len(post_text.split(chr(10)))}"
            
            # Return tuple: post_results, clarification_group, missing_fields_display, questions_display, answer1-5, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
            return (
                gr.Group(visible=True),   # post_results
                gr.Group(visible=False),  # clarification_group
                "",  # missing_fields_display
                "",  # questions_display
                "", "", "", "", "",  # answer1-5 (hidden)
                post_text,  # generated_post
                stats_text, # post_stats
                result["post_metadata"],    # post_metadata_display
                result["event_details"],    # event_details_display
                "\u2705 Post generated successfully! Review and approve below."  # workflow_status
            )
        
        # Clarification handlers
        def submit_answers_handler(*answers, progress=gr.Progress()):
            """Handle submission of clarification answers."""
            # Filter out empty answers and create answer dict
            answer_dict = {}
            for i, answer in enumerate(answers):
                if answer and answer.strip():
                    answer_dict[str(i+1)] = answer.strip()
            
            if not answer_dict:
                # Return tuple: clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
                return (
                    gr.Group(visible=True),  # clarification_group
                    gr.Group(visible=False), # post_results
                    "",  # generated_post
                    "",  # post_stats
                    {},  # post_metadata_display
                    {},  # event_details_display
                    "Please provide at least one answer to continue."  # workflow_status
                )
            
            # Continue workflow with answers
            result = workflow_adapter.continue_with_clarification(answer_dict, progress)
            
            if not result["success"]:
                # Return tuple: clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
                return (
                    gr.Group(visible=True),  # clarification_group
                    gr.Group(visible=False), # post_results
                    "",  # generated_post
                    "",  # post_stats
                    {},  # post_metadata_display
                    {},  # event_details_display
                    f"Error: {result.get('error', 'Unknown error')}"  # workflow_status
                )
            
            # Calculate stats
            post_text = result["refined_post"]
            word_count = len(post_text.split())
            char_count = len(post_text)
            stats_text = f"Words: {word_count} | Characters: {char_count} | Lines: {len(post_text.split(chr(10)))}"
            
            # Return tuple: clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
            return (
                gr.Group(visible=False),  # clarification_group
                gr.Group(visible=True),   # post_results
                post_text,               # generated_post
                stats_text,              # post_stats
                result["post_metadata"], # post_metadata_display
                result["event_details"], # event_details_display
                "✅ Post generated successfully with your additional information! Review and approve below."  # workflow_status
            )
        
        def skip_questions_handler(progress=gr.Progress()):
            """Skip clarification questions and continue with incomplete data."""
            # Continue workflow without additional answers
            result = workflow_adapter.continue_with_clarification({}, progress)
            
            if not result["success"]:
                # Return tuple: clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
                return (
                    gr.Group(visible=True),  # clarification_group
                    gr.Group(visible=False), # post_results
                    "",  # generated_post
                    "",  # post_stats
                    {},  # post_metadata_display
                    {},  # event_details_display
                    f"Error: {result.get('error', 'Unknown error')}"  # workflow_status
                )
            
            # Calculate stats
            post_text = result["refined_post"]
            word_count = len(post_text.split())
            char_count = len(post_text)
            stats_text = f"Words: {word_count} | Characters: {char_count} | Lines: {len(post_text.split(chr(10)))}"
            
            # Return tuple: clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status
            return (
                gr.Group(visible=False),  # clarification_group
                gr.Group(visible=True),   # post_results
                post_text,               # generated_post
                stats_text,              # post_stats
                result["post_metadata"], # post_metadata_display
                result["event_details"], # event_details_display
                "\u2705 Post generated successfully! Review and approve below."  # workflow_status
            )
        
        # Connect clarification buttons
        submit_answers_btn.click(
            submit_answers_handler,
            inputs=clarification_answers,
            outputs=[clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status]
        )
        
        skip_questions_btn.click(
            skip_questions_handler,
            outputs=[clarification_group, post_results, generated_post, post_stats, post_metadata_display, event_details_display, workflow_status]
        )
        
        create_post_btn.click(
            create_post_handler,
            inputs=[post_content, attachments, scheduled_date],
            outputs=[post_results, clarification_group, missing_fields_display, questions_display] + clarification_answers + [generated_post, post_stats, post_metadata_display, event_details_display, workflow_status]
        )
        
        def approve_post_handler(post_text):
            if not post_text.strip():
                return "Please generate a post first", gr.Textbox(visible=False)
            
            result = workflow_adapter.approve_and_save_post(post_text)
            
            if result["success"]:
                message = f"""
                ✅ Post approved and scheduled successfully!
                
                📝 Post Number: {result['post_number']}
                📅 Scheduled for: {result['scheduled_time']}
                💾 Saved to Google Sheets: {'Yes' if result['saved_to_sheet'] else 'No'}
                👤 Persona Updated: {'Yes' if result['persona_updated'] else 'No'}
                
                Your post will be automatically published at the scheduled time if the background scheduler is running.
                """
                return message, gr.Textbox(visible=True)
            else:
                return f"❌ Error: {result['error']}", gr.Textbox(visible=True)
        
        approve_btn.click(
            approve_post_handler,
            inputs=[generated_post],
            outputs=[approval_status, approval_status]
        )
        
        # Revise and regenerate handlers
        def show_revision_form():
            """Show the revision feedback form."""
            return {
                revision_feedback_group: gr.Group(visible=True),
                workflow_status: "📝 Please describe what changes you'd like to make to the post",
                revision_feedback: ""
            }
        
        def apply_revision_handler(post_text, feedback, progress=gr.Progress()):
            """Apply user's revision feedback to the post."""
            if not post_text.strip():
                return post_text, "", "Please generate a post first", gr.Group(visible=False)
            
            if not feedback.strip():
                return post_text, "", "Please provide feedback about what changes you'd like", gr.Group(visible=True)
            
            result = workflow_adapter.revise_post(post_text, feedback, progress)
            
            if result["success"]:
                stats_text = f"Words: {result['word_count']} | Characters: {result['char_count']} | Revision: {result['revision_count']}"
                return {
                    generated_post: result["revised_post"],
                    post_stats: stats_text,
                    workflow_status: "✅ Post revised successfully! Review the updated post above.",
                    revision_feedback_group: gr.Group(visible=False)
                }
            else:
                return {
                    generated_post: post_text,
                    post_stats: "",
                    workflow_status: f"❌ Revision error: {result['error']}",
                    revision_feedback_group: gr.Group(visible=False)
                }
        
        def cancel_revision_handler():
            """Cancel the revision process."""
            return {
                revision_feedback_group: gr.Group(visible=False),
                workflow_status: "Revision cancelled. You can still edit the post manually or try other options.",
                revision_feedback: ""
            }
        
        def regenerate_post_handler(progress=gr.Progress()):
            """Regenerate the post completely from scratch."""
            result = workflow_adapter.regenerate_post(progress)
            
            if result["success"]:
                stats_text = f"Words: {result['word_count']} | Characters: {result['char_count']} | Revision: {result['revision_count']}"
                return result["new_post"], stats_text, "✅ New post generated successfully!"
            else:
                return "", "", f"❌ Regeneration error: {result['error']}"
        
        # Connect revise button to show feedback form
        revise_btn.click(
            show_revision_form,
            outputs=[revision_feedback_group, workflow_status, revision_feedback]
        )
        
        # Connect apply revision button to process feedback
        apply_revision_btn.click(
            apply_revision_handler,
            inputs=[generated_post, revision_feedback],
            outputs=[generated_post, post_stats, workflow_status, revision_feedback_group]
        )
        
        # Connect cancel revision button
        cancel_revision_btn.click(
            cancel_revision_handler,
            outputs=[revision_feedback_group, workflow_status, revision_feedback]
        )
        
        # Connect regenerate button
        regenerate_btn.click(
            regenerate_post_handler,
            outputs=[generated_post, post_stats, workflow_status]
        )
        
        # Dashboard handlers
        def refresh_posts_handler():
            try:
                return get_scheduled_posts()
            except Exception as e:
                return pd.DataFrame({'Error': [f"Failed to load posts: {str(e)}"]})
        
        refresh_posts_btn.click(
            refresh_posts_handler,
            outputs=[posts_table]
        )
        
        def update_scheduler_status():
            try:
                status, info = get_scheduler_status()
                return status, info
            except Exception as e:
                return "❌ Error", f"Failed to check scheduler status: {str(e)}"
        
        def start_scheduler_handler():
            message = start_background_scheduler()
            status, info = get_scheduler_status()
            return message, status, info
        
        start_scheduler_btn.click(
            start_scheduler_handler,
            outputs=[scheduler_message, scheduler_status_text, scheduler_info]
        )
        
        def stop_scheduler_handler():
            message = stop_background_scheduler()
            status, info = get_scheduler_status()
            return message, status, info
        
        stop_scheduler_btn.click(
            stop_scheduler_handler,
            outputs=[scheduler_message, scheduler_status_text, scheduler_info]
        )
        
        # Settings handlers
        def check_status_handler():
            configured, message, details = check_system_status()
            return message
        
        check_status_btn.click(
            check_status_handler,
            outputs=[system_status]
        )
        
        # Clear button
        clear_btn.click(
            lambda: ("", None, None),
            outputs=[post_content, attachments, scheduled_date]
        )
        
        # Initialize scheduler status on load
        app.load(
            update_scheduler_status,
            outputs=[scheduler_status_text, scheduler_info]
        )
        
        # Initialize posts table on load  
        app.load(
            refresh_posts_handler,
            outputs=[posts_table]
        )
    
    return app


# Launch the application
if __name__ == "__main__":
    app = create_interface()
    
    # Launch with appropriate settings
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,  # Creates public link    
        show_error=True,
        debug=True
    )
