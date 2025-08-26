"""
Generate Post Node - LLM Stage 4: Creates the final LinkedIn post using all enriched data.
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


def generate_linkedin_post(state: WorkflowState) -> WorkflowState:
    """
    Uses Gemini Flash to generate a polished LinkedIn post from enriched data.
    
    Args:
        state: Current workflow state with all structured and enriched data
        
    Returns:
        Updated state with draft post
    """
    print("\n" + "-"*40)
    print("🤖 LLM Stage 4: Generating LinkedIn Post")
    print("-"*40)
    
    try:
        # Check for errors
        if state.get('error'):
            return state
        
        # Initialize Gemini Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.8,  # Higher temperature for creativity
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Get all relevant data
        post_metadata = state.get('post_metadata', {})
        event_details = state.get('event_details', {})
        persona_context = state.get('persona_context', {})
        persona_data = state.get('persona_data', {})
        
        # Extract writing preferences
        comm_prefs = persona_data.get('communication_preferences', {})
        use_emojis = comm_prefs.get('use_emojis', False)
        use_hashtags = comm_prefs.get('use_hashtags', True)
        
        # Create comprehensive system prompt
        system_prompt = f"""You are an expert LinkedIn content writer creating authentic, engaging posts.
        
        WRITING GUIDELINES:
        1. Start with a compelling hook (use the title_hook if provided, or create one)
        2. Tell a clear story with good flow: context → action → outcome → reflection
        3. Be authentic and personal, using "I" statements
        4. Include specific details and metrics where relevant
        5. End with either the engagement question provided or a call-to-action
        6. Keep paragraphs short (2-3 sentences max) for readability
        7. Use line breaks between main ideas
        
        TONE AND STYLE:
        - Tone: {persona_context.get('tone', 'professional yet approachable')}
        - Style: {persona_context.get('writing_style_notes', 'conversational and authentic')}
        - Voice: First person, {comm_prefs.get('style', 'casual writing')}
        - Emojis: {'Use sparingly for emphasis' if use_emojis else 'Do not use emojis'}
        - Length: 150-300 words (optimal for LinkedIn engagement)
        
        STRUCTURE:
        1. Hook/Opening (1-2 lines that grab attention)
        2. Context (What/When/Where)
        3. Your Role & Action (What you specifically did)
        4. Challenges & Solutions (If applicable)
        5. Outcome/Impact
        6. Key Learning/Reflection
        7. Acknowledgments (Tag people/organizations if mentioned)
        8. Engagement (Question or CTA)
        9. Hashtags (3-5 relevant ones at the end)
        
        Remember: This should sound like a real person sharing a genuine experience, not a corporate announcement.
        Write in a way that encourages likes, comments, and shares."""
        
        # Prepare the full context
        full_context = {
            "event_type": post_metadata.get('event_type', 'experience'),
            "title_hook": post_metadata.get('title_hook'),
            "date": post_metadata.get('date_of_event'),
            "description": event_details.get('description'),
            "role": event_details.get('role'),
            "tools_skills": event_details.get('tools_skills', []),
            "challenges": event_details.get('challenges'),
            "learnings": event_details.get('learnings'),
            "outcome": event_details.get('outcome'),
            "acknowledgements": event_details.get('acknowledgements', []),
            "engagement_question": event_details.get('engagement_question'),
            "persona_suggestions": event_details.get('persona_suggestions', {}),
            "career_alignment": persona_context.get('career_goal_alignment'),
            "values_reflected": persona_context.get('values_reflected'),
            "author_name": persona_data.get('basic_info', {}).get('full_name', 'I'),
            "current_role": persona_data.get('basic_info', {}).get('current_role', '')
        }
        
        user_message = f"""Generate a LinkedIn post based on this information:
        
        {json.dumps(full_context, indent=2)}
        
        Create an authentic, engaging post that reflects the author's voice and experience.
        {f"Include these hashtags: {comm_prefs.get('hashtag_style', 'relevant technical and professional hashtags')}" if use_hashtags else "Do not include hashtags"}
        
        The post should feel natural and conversational while maintaining professionalism."""
        
        # Get post generation response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("✍️ Crafting your LinkedIn post...")
        response = llm.invoke(messages)
        
        # Extract the generated post
        draft_post = response.content.strip()
        
        # Store the draft post
        state['draft_post'] = draft_post
        
        # Calculate post metrics
        word_count = len(draft_post.split())
        char_count = len(draft_post)
        
        print("\n✅ LinkedIn post generated successfully!")
        print(f"   • Length: {word_count} words, {char_count} characters")
        print(f"   • Style: {persona_context.get('tone', 'Professional')}")
        
        # Show preview (first 150 chars)
        preview = draft_post[:150] + "..." if len(draft_post) > 150 else draft_post
        print(f"\n📄 Preview: {preview}")
        
        return state
        
    except Exception as e:
        state['error'] = f"Error generating post: {str(e)}"
        state['error_node'] = "generate_post"
        print(f"❌ Error: {str(e)}")
        return state
