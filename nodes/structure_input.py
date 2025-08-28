"""
Structure Input Node - LLM Stage 1: Converts rough user input into structured JSON.
"""

import json
import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import sys
sys.path.append('..')
from state import WorkflowState, PostMetadata, EventDetails
from .utils import parse_llm_json_response

load_dotenv()


def structure_user_input(state: WorkflowState) -> WorkflowState:
    """
    Uses Gemini Flash to structure raw user input into organized JSON format.
    
    Args:
        state: Current workflow state containing raw_input
        
    Returns:
        Updated state with structured post_metadata and event_details
    """
    print("\n" + "-"*40)
    print("🤖 LLM Stage 1: Structuring Input")
    print("-"*40)
    
    try:
        # Check for errors
        if state.get('error'):
            return state
        
        # Initialize Gemini Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.7,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Create system prompt
        system_prompt = """You are an expert at structuring LinkedIn post content. 
        Convert the user's rough notes into a well-organized JSON structure.
        
        Analyze the input and extract the following information:
        
        POST METADATA:
        - event_type: Categorize as one of: project | hackathon | internship | competition | achievement | learning | experience | collaboration | talk/event
        - title_hook: Create a catchy first line if not provided (optional)
        - date_of_event: Extract date if mentioned (format: YYYY-MM-DD)
        
        EVENT DETAILS:
        - description: Clear context of what happened
        - role: What the user specifically did
        - tools_skills: List of technologies/skills used (as array)
        - challenges: Problems faced and how they were solved
        - learnings: Key personal takeaways
        - outcome: Results, recognition, or usefulness
        - acknowledgements: People or organizations to thank/tag (as array)
        - engagement_question: A question to drive interaction (you can suggest one)
        - attachments: Keep any mentioned media paths (as array)
        
        Output ONLY valid JSON with these two objects:
        {
            "post_metadata": {...},
            "event_details": {...}
        }
        
        If information is not explicitly provided, use null for that field.
        Be thorough but don't make up information that isn't implied in the input."""
        
        # Create user message with the raw input
        user_message = f"""Please structure the following rough notes into JSON format:
        
        {state['raw_input']}
        
        {f"Note: User has provided these attachment paths: {state['media_paths']}" if state.get('media_paths') else ""}"""
        
        # Get LLM response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("📝 Processing raw input...")
        response = llm.invoke(messages)
        
        # Parse JSON response using robust utility function
        fallback_data = {
            "post_metadata": {},
            "event_details": {}
        }
        structured_data = parse_llm_json_response(response.content, fallback_data)
        
        # Update state with structured data
        state['post_metadata'] = structured_data.get('post_metadata', {})
        state['event_details'] = structured_data.get('event_details', {})
        
        # Add media paths if provided
        if state.get('media_paths'):
            if not state['event_details'].get('attachments'):
                state['event_details']['attachments'] = state['media_paths']
            else:
                state['event_details']['attachments'].extend(state['media_paths'])
        
        print("✅ Successfully structured input into JSON format")
        print(f"   • Event Type: {state['post_metadata'].get('event_type', 'Not specified')}")
        print(f"   • Skills/Tools: {len(state['event_details'].get('tools_skills', [])) if state['event_details'].get('tools_skills') else 0} identified")
        
        return state
        
    except json.JSONDecodeError as e:
        state['error'] = f"Failed to parse LLM response as JSON: {str(e)}"
        state['error_node'] = "structure_input"
        print(f"❌ JSON parsing error: {str(e)}")
        return state
    except Exception as e:
        state['error'] = f"Error in structuring input: {str(e)}"
        state['error_node'] = "structure_input"
        print(f"❌ Error: {str(e)}")
        return state
