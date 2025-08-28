"""
Automatic LinkedIn Poster - Main Workflow Orchestrator
Uses LangGraph to manage the multi-stage LLM pipeline for post creation.
"""

import sys
import os
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
from credentials_loader import load_credentials

# Import state management
from state import WorkflowState

# Import all node functions - with validation
try:
    from nodes.input_collector import collect_user_input
    from nodes.structure_input import structure_user_input
    from nodes.validate_completeness import validate_and_complete
    from nodes.enrich_persona import enrich_with_persona
    from nodes.generate_post import generate_linkedin_post
    from nodes.refine_post import refine_and_humanize_post
    from nodes.user_approval import get_user_approval
    from nodes.save_to_sheet import save_post_to_sheet
    from nodes.update_persona import update_persona_from_post
except ImportError as e:
    print(f"❌ Error importing node modules: {e}")
    print("Please ensure all node files are present in the 'nodes/' directory.")
    sys.exit(1)

# Load environment variables
load_dotenv()


def check_error(state: WorkflowState) -> str:
    """
    Check if there's an error in the state and route accordingly.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node to execute or END
    """
    if state.get('error'):
        return END
    return "continue"


def check_approval(state: WorkflowState) -> str:
    """
    Check if post is approved and route accordingly.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node based on approval status
    """
    if state.get('error'):
        return END
    
    if state.get('post_approved'):
        return "save_to_sheet"
    
    # Check if user wants to regenerate completely
    if state.get('user_feedback') == 'regenerate_completely':
        return "generate_post"
    
    # Otherwise, go back to approval for another review
    return "user_approval"


def create_workflow() -> StateGraph:
    """
    Creates and configures the LangGraph workflow for LinkedIn post creation.
    
    Returns:
        Configured StateGraph object
    """
    print("\n" + "="*60)
    print("🚀 AUTOMATIC LINKEDIN POSTER")
    print("="*60)
    print("\nInitializing workflow engine...")
    
    # Create the state graph
    workflow = StateGraph(WorkflowState)
    
    # Add all nodes to the graph
    workflow.add_node("collect_input", collect_user_input)
    workflow.add_node("structure_input", structure_user_input)
    workflow.add_node("validate_completeness", validate_and_complete)
    workflow.add_node("enrich_persona", enrich_with_persona)
    workflow.add_node("generate_post", generate_linkedin_post)
    workflow.add_node("refine_post", refine_and_humanize_post)
    workflow.add_node("user_approval", get_user_approval)
    workflow.add_node("save_to_sheet", save_post_to_sheet)
    workflow.add_node("update_persona", update_persona_from_post)
    
    # Define the edges (workflow flow)
    # Start with input collection
    workflow.set_entry_point("collect_input")
    
    # Linear flow through LLM stages
    workflow.add_conditional_edges(
        "collect_input",
        check_error,
        {
            "continue": "structure_input",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "structure_input",
        check_error,
        {
            "continue": "validate_completeness",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "validate_completeness",
        check_error,
        {
            "continue": "enrich_persona",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "enrich_persona",
        check_error,
        {
            "continue": "generate_post",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "generate_post",
        check_error,
        {
            "continue": "refine_post",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "refine_post",
        check_error,
        {
            "continue": "user_approval",
            END: END
        }
    )
    
    # Approval can loop back for revisions or proceed to save
    workflow.add_conditional_edges(
        "user_approval",
        check_approval,
        {
            "save_to_sheet": "save_to_sheet",
            "generate_post": "generate_post",
            "user_approval": "user_approval",
            END: END
        }
    )
    
    # Save to sheet then update persona
    workflow.add_edge("save_to_sheet", "update_persona")
    
    # Persona update is the final step
    workflow.add_edge("update_persona", END)
    
    # Compile the workflow
    memory = MemorySaver()
    compiled_workflow = workflow.compile(checkpointer=memory)
    
    print("✅ Workflow engine initialized successfully!")
    
    return compiled_workflow


def display_summary(state: Dict[str, Any]):
    """
    Display a summary of the completed workflow.
    
    Args:
        state: Final workflow state
    """
    print("\n" + "="*60)
    print("📊 WORKFLOW SUMMARY")
    print("="*60)
    
    if state.get('error'):
        print(f"\n❌ Workflow ended with error:")
        print(f"   Error: {state['error']}")
        print(f"   Node: {state.get('error_node', 'Unknown')}")
        return
    
    if state.get('saved_to_sheet'):
        print("\n✅ Post created and scheduled successfully!")
        print(f"\n📝 Post Details:")
        print(f"   • Post Number: {state.get('post_number', 'N/A')}")
        print(f"   • Scheduled for: {state.get('scheduled_time', 'N/A')}")
        print(f"   • Revisions made: {state.get('revision_count', 0)}")
        print(f"   • Word count: {len(state.get('final_post', '').split())} words")
        
        if state.get('media_paths'):
            print(f"   • Attachments: {len(state['media_paths'])} file(s)")
        
        # Display persona update information
        if state.get('persona_updated'):
            print(f"   • Persona updated: Yes")
            updates = state.get('persona_updates', {})
            update_count = sum(len(v) if isinstance(v, list) else 1 for v in updates.values() if v)
            if update_count > 0:
                print(f"   • New information added: {update_count} item(s)")
        else:
            print(f"   • Persona updated: No new information found")
        
        print(f"\n📌 Next Steps:")
        print(f"   1. Your post has been saved to Google Sheets")
        print(f"   2. Run 'python background.py' to start the auto-poster")
        print(f"   3. The post will be published at the scheduled time")
        if state.get('persona_updated'):
            print(f"   4. Your persona has been automatically updated with new information")
    else:
        print("\n⚠️ Post was not saved to Google Sheets")


def main():
    """
    Main entry point for the LinkedIn post creation workflow.
    """
    try:
        # Check if credentials exist and can be loaded
        try:
            credentials = load_credentials()
            print("✅ Credentials loaded successfully!")
        except FileNotFoundError:
            print("\n⚠️ Error: credentials.json not found!")
            print("Please run 'python setup.py' first to configure the system.")
            sys.exit(1)
        except Exception as e:
            print(f"\n⚠️ Error loading credentials: {e}")
            print("Please check your credentials.json file or run 'python setup.py' to reconfigure.")
            sys.exit(1)
        
        # Create and run the workflow
        workflow = create_workflow()
        
        # Initialize empty state
        initial_state = WorkflowState()
        
        # Configuration for the workflow execution
        config = {
            "configurable": {
                "thread_id": "linkedin-post-creation"
            }
        }
        
        print("\nStarting LinkedIn post creation workflow...\n")
        
        # Execute the workflow
        final_state = None
        for state in workflow.stream(initial_state, config):
            # The stream yields dictionaries with node names as keys
            for node_name, node_state in state.items():
                if node_name != "__end__":
                    final_state = node_state
        
        # Display summary
        if final_state:
            display_summary(final_state)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Workflow cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error in workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
