"""
Input Collector Node - Gathers initial user input for LinkedIn post creation.
"""

from datetime import datetime
import json
from pathlib import Path
import sys
sys.path.append('..')
from state import WorkflowState
from credentials_loader import get_persona_path


def collect_user_input(state: WorkflowState) -> WorkflowState:
    """
    Collects initial user input including rough notes, attachments, and scheduling.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with user input
    """
    print("\n" + "="*60)
    print("LINKEDIN POST CREATOR - INPUT COLLECTION")
    print("="*60)
    
    try:
        # Load persona data using credentials_loader
        persona_path = get_persona_path()
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona_data = json.load(f)
        
        print(f"\n✅ Loaded persona for: {persona_data.get('basic_info', {}).get('full_name', 'User')}")
        
        # Collect rough notes
        print("\n" + "-"*40)
        print("Step 1: Share Your Content")
        print("-"*40)
        print("\nTell me about what you want to share on LinkedIn.")
        print("This can be rough notes, bullet points, or a brief description.")
        print("(Type 'END' on a new line when finished)\n")
        
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        
        raw_input = '\n'.join(lines)
        
        if not raw_input.strip():
            state['error'] = "No input provided"
            state['error_node'] = "input_collector"
            return state
        
        # Collect attachments
        print("\n" + "-"*40)
        print("Step 2: Attachments (Optional)")
        print("-"*40)
        print("\nDo you have any images or documents to attach?")
        has_attachments = input("Enter 'yes' or 'no': ").strip().lower()
        
        media_paths = []
        if has_attachments == 'yes':
            print("\nEnter file paths (one per line, type 'DONE' when finished):")
            while True:
                path = input().strip()
                if path.upper() == 'DONE':
                    break
                if path:
                    # Validate path exists
                    if Path(path).exists():
                        media_paths.append(path)
                        print(f"✅ Added: {path}")
                    else:
                        print(f"⚠️ File not found: {path}")
        
        # Collect scheduling information
        print("\n" + "-"*40)
        print("Step 3: Scheduling")
        print("-"*40)
        print("\nWhen should this post be published?")
        print("Format: YYYY-MM-DD HH:MM (24-hour format)")
        print("Example: 2025-08-20 14:30")
        print("(Press Enter to post immediately)")
        
        scheduled_time = input("\nScheduled time: ").strip()
        
        if scheduled_time:
            # Validate datetime format
            try:
                datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")
            except ValueError:
                print("⚠️ Invalid datetime format. Using immediate posting.")
                scheduled_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            scheduled_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            print(f"📅 Will post immediately at: {scheduled_time}")
        
        # Update state
        state['raw_input'] = raw_input
        state['media_paths'] = media_paths if media_paths else None
        state['scheduled_time'] = scheduled_time
        state['persona_data'] = persona_data
        state['revision_count'] = 0
        
        print("\n✅ Input collected successfully!")
        print(f"   • Content length: {len(raw_input)} characters")
        print(f"   • Attachments: {len(media_paths) if media_paths else 0}")
        print(f"   • Scheduled for: {scheduled_time}")
        
        return state
        
    except FileNotFoundError as e:
        state['error'] = f"Configuration file not found: {str(e)}"
        state['error_node'] = "input_collector"
        return state
    except json.JSONDecodeError as e:
        state['error'] = f"Invalid JSON in configuration: {str(e)}"
        state['error_node'] = "input_collector"
        return state
    except Exception as e:
        state['error'] = f"Unexpected error in input collection: {str(e)}"
        state['error_node'] = "input_collector"
        return state
