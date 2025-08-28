"""
User Approval Node - Handles user review and feedback for post revisions.
"""

import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import sys
sys.path.append('..')
from state import WorkflowState

load_dotenv()


def get_user_approval(state: WorkflowState) -> WorkflowState:
    """
    Presents the draft post to the user for approval and handles revision requests.
    
    Args:
        state: Current workflow state with draft post
        
    Returns:
        Updated state with approval status or revision feedback
    """
    print("\n" + "="*60)
    print("📝 POST REVIEW & APPROVAL")
    print("="*60)
    
    try:
        # Check for errors
        if state.get('error'):
            return state
        
        # Display the draft post
        print("\nHere's your generated LinkedIn post:\n")
        print("-"*40)
        print(state['draft_post'])
        print("-"*40)
        
        # Get user feedback
        print("\n🔍 Review Options:")
        print("1. Approve - Post looks great, schedule it!")
        print("2. Revise - I'd like to make some changes")
        print("3. Regenerate - Start over with a completely new version")
        print("4. Cancel - Exit without saving")
        
        choice = input("\nYour choice (1-4): ").strip()
        
        if choice == '1':
            # Approved
            state['post_approved'] = True
            state['final_post'] = state['draft_post']
            print("\n✅ Post approved! Moving to scheduling...")
            return state
            
        elif choice == '2':
            # Request revisions
            print("\n📝 Please describe what changes you'd like:")
            print("(Be specific about what to add, remove, or modify)")
            feedback = input("\nYour feedback: ").strip()
            
            if not feedback:
                print("⚠️ No feedback provided. Keeping original post.")
                state['post_approved'] = True
                state['final_post'] = state['draft_post']
                return state
            
            # Use LLM to revise the post based on feedback
            state = revise_post(state, feedback)
            
            # Increment revision count
            state['revision_count'] = state.get('revision_count', 0) + 1
            
            # Set approved to False to trigger another approval cycle
            state['post_approved'] = False
            state['user_feedback'] = feedback
            
            return state
            
        elif choice == '3':
            # Regenerate completely
            print("\n🔄 Regenerating post from scratch...")
            state['draft_post'] = None
            state['post_approved'] = False
            state['user_feedback'] = "regenerate_completely"
            state['revision_count'] = state.get('revision_count', 0) + 1
            return state
            
        elif choice == '4':
            # Cancel
            state['error'] = "User cancelled the post creation"
            state['error_node'] = "user_approval"
            print("\n❌ Post creation cancelled.")
            return state
            
        else:
            print("⚠️ Invalid choice. Please try again.")
            # Return with approved = False to loop back
            state['post_approved'] = False
            return state
            
    except Exception as e:
        state['error'] = f"Error in approval process: {str(e)}"
        state['error_node'] = "user_approval"
        print(f"❌ Error: {str(e)}")
        return state


def revise_post(state: WorkflowState, feedback: str) -> WorkflowState:
    """
    Uses LLM to revise the post based on user feedback.
    
    Args:
        state: Current workflow state
        feedback: User's revision feedback
        
    Returns:
        State with revised draft post
    """
    try:
        # Initialize Gemini Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.6,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Create revision prompt
        system_prompt = """You are an expert LinkedIn post editor. 
        Your task is to revise the given post based on specific user feedback.
        
        REVISION GUIDELINES:
        1. Make only the changes requested by the user
        2. Preserve the overall structure and tone unless specifically asked to change
        3. Maintain the same persona and writing style
        4. Keep all good elements that the user didn't ask to change
        5. Ensure the revised post flows naturally
        
        Output only the revised post text, nothing else."""
        
        user_message = f"""Original LinkedIn Post:
        {state['draft_post']}
        
        User Feedback:
        {feedback}
        
        Please revise the post according to this feedback while keeping everything else that works well."""
        
        # Get revision
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("\n🔄 Revising post based on your feedback...")
        response = llm.invoke(messages)
        
        # Update draft with revision
        state['draft_post'] = response.content.strip()
        
        print("✅ Post revised successfully!")
        
        return state
        
    except Exception as e:
        print(f"⚠️ Error revising post: {str(e)}")
        print("Keeping original version.")
        return state
