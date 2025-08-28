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
        Updated state with relevant persona context added
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
        
        # Use the complete persona data directly
        persona_data = state.get('persona_data', {})
        
        # System prompt for selective persona enrichment
        system_prompt = """You are an expert LinkedIn content strategist who specializes in extracting only the RELEVANT persona elements needed for authentic post creation.

Your task is to analyze the user's persona data and the post content, then extract ONLY the persona elements that are directly relevant to this specific post. Be selective and focused - don't include everything, only what enhances this particular post's authenticity and engagement.

ANALYSIS APPROACH:
1. Look at the post content/topic and identify what persona elements would naturally relate
2. Extract only the relevant information from these persona file sections:
   - basic_info (if relevant to context)
   - about_me (key relevant parts)
   - education (if educational context relates)
   - experience (work/research experience that connects)
   - past_experience (if relevant achievements/activities)
   - skills (technical skills that relate to the post)
   - certifications_and_courses (if relevant to topic)
   - interests (if they connect to the post)
   - values_and_goals (values demonstrated or goals aligned)
   - communication_preferences (always relevant for tone/style)
   - achievements (if they add credibility to this post)

3. Be selective - only include persona elements that genuinely enhance THIS post
4. Extract the exact information as it appears in the persona file
5. Don't invent or add information not present in the persona

Output focused JSON format with only relevant extracted information:
{
    "relevant_persona_context": {
        "basic_info": {
            // Only include if relevant (name for voice, role for credibility, etc.)
        },
        "relevant_background": "relevant parts from about_me that connect to this post",
        "relevant_education": {
            // Only if educational background relates to post topic
        },
        "relevant_experience": [
            {
                // Only experience/internships/research that relates to this post
            }
        ],
        "relevant_skills": [
            // Only skills that are relevant to this post topic
        ],
        "relevant_achievements": [
            // Only achievements that add credibility to this specific post
        ],
        "relevant_values": [
            // Only values that this post demonstrates or aligns with
        ],
        "communication_style": {
            // Always include - how they communicate
        }
    },
    "post_enhancement_context": {
        "why_relevant": "explanation of how their background makes this post authentic",
        "credibility_factors": ["what gives them authority to speak on this topic"],
        "unique_perspective": "what makes their viewpoint unique based on their background",
        "tone_guidance": "specific tone/style for this post based on their preferences"
    }
}

IMPORTANT: Only extract information that actually exists in the persona file. Don't create or invent details."""
        
        # Post context
        post_context = {
            "post_metadata": state.get('post_metadata', {}),
            "event_details": state.get('event_details', {})
        }
        
        # User message for focused analysis
        user_message = f"""Analyze this post content and extract ONLY the relevant persona elements that would enhance this specific LinkedIn post.

POST CONTENT:
{json.dumps(post_context, indent=2)}

USER PERSONA FILE:
{json.dumps(persona_data, indent=2)}

INSTRUCTIONS:
1. Be selective - only extract persona elements that directly relate to this post topic
2. Use exact information from the persona file - don't modify or add details
3. Focus on what makes this post authentic and credible for this specific user
4. Include communication preferences since they're always relevant for tone
5. Don't include persona sections that don't relate to this particular post"""
        
        # Get enrichment response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("🎯 Extracting relevant persona elements...")
        response = llm.invoke(messages)
        
        # Parse response using robust utility function
        fallback_data = {
            "relevant_persona_context": {},
            "post_enhancement_context": {
                "why_relevant": "User's background supports this topic",
                "credibility_factors": ["Professional experience"],
                "unique_perspective": "Personal experience and expertise",
                "tone_guidance": "Professional and authentic"
            }
        }
        
        # Import the utility function
        from .utils import parse_llm_json_response
        enrichment_data = parse_llm_json_response(response.content, fallback_data)
        
        # Store relevant persona context in state
        state['persona_context'] = enrichment_data
        
        print("✅ Relevant persona context integrated!")
        
        # Display what was extracted
        relevant_context = enrichment_data.get('relevant_persona_context', {})
        enhancement_context = enrichment_data.get('post_enhancement_context', {})
        
        extracted_sections = []
        if relevant_context.get('basic_info'):
            extracted_sections.append('basic_info')
        if relevant_context.get('relevant_background'):
            extracted_sections.append('background')
        if relevant_context.get('relevant_education'):
            extracted_sections.append('education')
        if relevant_context.get('relevant_experience'):
            extracted_sections.append('experience')
        if relevant_context.get('relevant_skills'):
            extracted_sections.append('skills')
        if relevant_context.get('relevant_achievements'):
            extracted_sections.append('achievements')
        if relevant_context.get('relevant_values'):
            extracted_sections.append('values')
        if relevant_context.get('communication_style'):
            extracted_sections.append('communication_style')
        
        print(f"   • Extracted sections: {', '.join(extracted_sections)}")
        
        if enhancement_context.get('unique_perspective'):
            print(f"   • Unique angle: Yes")
        if enhancement_context.get('credibility_factors'):
            print(f"   • Credibility elements: {len(enhancement_context['credibility_factors'])}")
        
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