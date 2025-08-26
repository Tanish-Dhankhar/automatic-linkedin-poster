"""
Enrich Persona Node - LLM Stage 3: Integrates complete persona context into the post data.
"""

import json
import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import sys
sys.path.append('..')
from state import WorkflowState

load_dotenv()


def enrich_with_persona(state: WorkflowState) -> WorkflowState:
    """
    Uses Gemini Flash to analyze post content and integrate relevant persona elements.
    
    Args:
        state: Current workflow state with structured data and persona
        
    Returns:
        Updated state with persona context added
    """
    print("\n" + "-"*40)
    print("🤖 LLM Stage 3: Persona Enrichment")
    print("-"*40)
    
    try:
        # Check for errors
        if state.get('error'):
            return state
        
        # Initialize Gemini Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.6,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # 🔑 Use the complete persona data directly
        persona_data = state.get('persona_data', {})
        
        # System prompt for persona enrichment
        system_prompt = """You are an expert at personalizing LinkedIn content based on user personas.
        
Your task is to analyze the post content and the complete persona file to identify:
1. The most appropriate tone and writing style for this post
2. Relevant experiences or background that connect to the post topic
3. How this post aligns with the user's career goals and values

Be selective - only pull in persona elements that genuinely enhance the post's authenticity.
Don't force connections that aren't natural.

Output JSON format:
{
    "persona_context": {
        "tone": "specific tone description based on persona and content",
        "relevant_experience": "specific background/experience that relates to this post",
        "career_goal_alignment": "how this post/achievement aligns with their goals",
        "values_reflected": "which personal values this demonstrates",
        "writing_style_notes": "specific style guidance for this post"
    },
    "persona_suggestions": {
        "skills_to_highlight": ["skill1", "skill2"],
        "achievements_to_reference": "relevant past achievement if applicable",
        "professional_identity": "how to position themselves"
    }
}"""
        
        # Post context (still selective)
        post_context = {
            "post_metadata": state.get('post_metadata', {}),
            "event_details": state.get('event_details', {})
        }
        
        # 🔑 Send full persona JSON instead of filtered summary
        user_message = f"""Analyze this LinkedIn post content with the complete persona file.

POST CONTENT:
{json.dumps(post_context, indent=2)}

USER PERSONA (Full JSON):
{json.dumps(persona_data, indent=2)}

Please identify the most relevant persona elements that would make this post more authentic and engaging."""
        
        # Get enrichment response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("🎯 Analyzing persona relevance...")
        response = llm.invoke(messages)
        
        # Parse response
        response_text = response.content.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        enrichment_data = json.loads(response_text)
        
        # Update state with persona context
        state['persona_context'] = enrichment_data.get('persona_context', {})
        
        # Also store suggestions for the post generation phase
        if 'persona_suggestions' in enrichment_data:
            if not state.get('event_details'):
                state['event_details'] = {}
            state['event_details']['persona_suggestions'] = enrichment_data['persona_suggestions']
        
        print("✅ Persona context integrated successfully!")
        print(f"   • Tone: {state['persona_context'].get('tone', 'Not specified')}")
        print(f"   • Career Alignment: {'Yes' if state['persona_context'].get('career_goal_alignment') else 'No'}")
        
        # Show name if available
        name = persona_data.get('basic_info', {}).get('full_name', '') or persona_data.get('name', '')
        if name:
            print(f"   • Writing as: {name}")
        
        return state
        
    except json.JSONDecodeError as e:
        state['error'] = f"Failed to parse persona enrichment response: {str(e)}"
        state['error_node'] = "enrich_persona"
        print(f"❌ JSON parsing error: {str(e)}")
        return state
    except Exception as e:
        state['error'] = f"Error in persona enrichment: {str(e)}"
        state['error_node'] = "enrich_persona"
        print(f"❌ Error: {str(e)}")
        return state
