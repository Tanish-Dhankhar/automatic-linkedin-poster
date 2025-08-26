"""
Validate Completeness Node - LLM Stage 2: Checks if enough information is present and asks clarifying questions.
"""

import json
import os
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import sys
sys.path.append('..')
from state import WorkflowState

load_dotenv()


def validate_and_complete(state: WorkflowState) -> WorkflowState:
    """
    Uses Gemini Flash to validate completeness and gather missing information.
    
    Args:
        state: Current workflow state with structured data
        
    Returns:
        Updated state with validation results and user responses
    """
    print("\n" + "-"*40)
    print("🤖 LLM Stage 2: Validating Completeness")
    print("-"*40)
    
    try:
        # Check for errors
        if state.get('error'):
            return state
        
        # Initialize Gemini Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.5,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Create system prompt for validation
        system_prompt = """You are an expert LinkedIn content validator.
        Review the structured post data and determine if it has enough information to create an authentic and engaging LinkedIn post.
        
        Critical fields that should have meaningful content:
        1. Description - Clear context of what happened
        2. Role - What the user specifically did
        3. Learnings OR Outcome - At least one should be present
        4. Tools/Skills - For technical posts
        
        Nice to have:
        - Challenges faced
        - Acknowledgements
        - Engagement question
        
        Analyze the data and:
        1. Determine if the post has enough substance (return "is_complete": true/false)
        2. If incomplete, generate 2-3 specific questions to gather missing critical information
        3. Questions should be conversational and specific to the context
        
        Output JSON format:
        {
            "is_complete": boolean,
            "missing_fields": ["field1", "field2"],
            "clarifying_questions": ["question1", "question2", "question3"],
            "validation_notes": "Brief explanation of what's missing"
        }"""
        
        # Prepare current data for validation
        current_data = {
            "post_metadata": state.get('post_metadata', {}),
            "event_details": state.get('event_details', {})
        }
        
        user_message = f"""Please validate the completeness of this LinkedIn post data:
        
        {json.dumps(current_data, indent=2)}
        
        Check if there's enough information to create an authentic and engaging post."""
        
        # Get validation response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("🔍 Analyzing content completeness...")
        response = llm.invoke(messages)
        
        # Parse validation response
        response_text = response.content.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        validation_result = json.loads(response_text)
        
        # Update state with validation results
        state['is_complete'] = validation_result.get('is_complete', False)
        state['missing_fields'] = validation_result.get('missing_fields', [])
        state['clarifying_questions'] = validation_result.get('clarifying_questions', [])
        
        if state['is_complete']:
            print("✅ Content is complete and ready for post generation!")
            return state
        
        # If not complete, ask clarifying questions
        print("\n⚠️ Additional information needed for a complete post.")
        print(f"Missing fields: {', '.join(state['missing_fields'])}")
        print("\nPlease answer these questions to enhance your post:\n")
        
        user_responses = {}
        for i, question in enumerate(state['clarifying_questions'], 1):
            print(f"{i}. {question}")
            answer = input("   Your answer: ").strip()
            user_responses[f"question_{i}"] = {
                "question": question,
                "answer": answer
            }
        
        state['user_responses'] = user_responses
        
        # Now merge the responses back into the structured data
        if user_responses:
            print("\n📝 Updating post data with your responses...")
            
            # Create prompt to merge responses
            merge_prompt = """You are helping update LinkedIn post data with user's responses to clarifying questions.
            
            Take the user's responses and intelligently merge them into the appropriate fields in the event_details.
            Don't overwrite existing good content, but enhance and complete it.
            
            Output the updated event_details JSON object only."""
            
            merge_message = f"""Current event details:
            {json.dumps(state.get('event_details', {}), indent=2)}
            
            User responses to clarifying questions:
            {json.dumps(user_responses, indent=2)}
            
            Please merge these responses into the event_details appropriately."""
            
            merge_messages = [
                SystemMessage(content=merge_prompt),
                HumanMessage(content=merge_message)
            ]
            
            merge_response = llm.invoke(merge_messages)
            
            # Parse merged data
            merged_text = merge_response.content.strip()
            if "```json" in merged_text:
                merged_text = merged_text.split("```json")[1].split("```")[0].strip()
            elif "```" in merged_text:
                merged_text = merged_text.split("```")[1].split("```")[0].strip()
            
            updated_details = json.loads(merged_text)
            state['event_details'] = updated_details
            state['is_complete'] = True
            
            print("✅ Post data updated successfully!")
        
        return state
        
    except json.JSONDecodeError as e:
        state['error'] = f"Failed to parse validation response: {str(e)}"
        state['error_node'] = "validate_completeness"
        print(f"❌ JSON parsing error: {str(e)}")
        return state
    except Exception as e:
        state['error'] = f"Error in validation: {str(e)}"
        state['error_node'] = "validate_completeness"
        print(f"❌ Error: {str(e)}")
        return state

