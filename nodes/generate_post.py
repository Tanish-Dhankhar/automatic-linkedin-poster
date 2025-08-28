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
        
        # Get all data from state
        post_metadata = state.get('post_metadata', {})
        event_details = state.get('event_details', {})
        persona_context = state.get('persona_context', {})
        persona_data = state.get('persona_data', {})
        
        # Create comprehensive system prompt
        system_prompt = """You are an expert LinkedIn content writer creating authentic, engaging posts that sound exactly like the person would write them.

Your task is to generate a LinkedIn post using ALL the provided context - the post content, complete persona data, and enriched persona context. Write in the user's authentic voice using their exact communication style and preferences.

WRITING APPROACH:
1. Use the person's authentic voice and communication style from their persona
2. Incorporate their technical background and expertise naturally
3. Reflect their values, motivations, and personality in the writing
4. Include relevant experience/education that adds credibility
5. Follow their communication preferences exactly (tone, emojis, hashtags, style)
6. Make it sound like THEY wrote it, not a generic LinkedIn post

STRUCTURE FOR LINKEDIN POSTS:
1. Hook/Opening (1-2 lines that grab attention)
2. Context Setting (What/When/Where - brief background)
3. Your Role & Actions (What you specifically did/experienced)
4. Challenges & Process (If applicable - how you approached it)
5. Outcomes & Results (What you achieved/learned)
6. Key Insights/Reflection (Your personal takeaways)
7. Future Perspective (How this connects to your goals/journey)
8. Acknowledgments (Thank relevant people/organizations)
9. Engagement (Question or call-to-action for comments)
10. Hashtags (Based on their preferences and relevant to content)

AUTHENTICITY REQUIREMENTS:
- Write in first person using their natural language patterns
- Include technical details that demonstrate their expertise
- Show their personality and values through the writing
- Use their preferred tone and communication style
- Follow their emoji and hashtag preferences exactly
- Make it feel personal and genuine, not corporate
- Include specific details that only they would know/mention

ENGAGEMENT OPTIMIZATION:
- Start with a compelling hook that makes people want to read more
- Use short paragraphs and line breaks for mobile readability
- Include specific metrics, tools, or outcomes when available
- End with a thoughtful question or call-to-action
- Optimize length for LinkedIn (150-300 words typically performs best)

Remember: This should sound like the actual person sharing their genuine experience, using their voice, style, and expertise. Every detail should feel authentic to their background and personality."""
        
        # User message with focused context
        user_message = f"""Generate an authentic LinkedIn post using the provided context:

POST CONTENT DATA:
{json.dumps(post_metadata, indent=2)}

EVENT DETAILS:
{json.dumps(event_details, indent=2)}

ENRICHED PERSONA CONTEXT (Contains all relevant persona information):
{json.dumps(persona_context, indent=2)}

INSTRUCTIONS:
1. Write in their authentic voice using their exact communication preferences
2. Incorporate their technical expertise and background naturally
3. Reflect their values, personality, and motivations
4. Use their preferred style for hashtags, emojis, and tone
5. Include specific details from their experience that add credibility
6. Make it sound exactly like they would write it
7. Ensure it's engaging and encourages interaction
8. Follow LinkedIn best practices for formatting and structure

Generate a post that captures their unique voice and expertise while being engaging and professional."""
        
        # Get post generation response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        print("✍️ Generating authentic LinkedIn post...")
        print("   • Analyzing complete persona context")
        print("   • Applying authentic voice and style")
        print("   • Incorporating technical expertise")
        print("   • Ensuring engagement optimization")
        
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
        
        # Extract style info from persona for display
        comm_prefs = persona_data.get('communication_preferences', {})
        tone = comm_prefs.get('tone', 'Professional')
        print(f"   • Style: {tone}")
        
        # Show preview (first 150 chars)
        preview = draft_post[:150] + "..." if len(draft_post) > 150 else draft_post
        print(f"\n📄 Preview: {preview}")
        
        return state
        
    except Exception as e:
        state['error'] = f"Error generating post: {str(e)}"
        state['error_node'] = "generate_post"
        print(f"❌ Error: {str(e)}")
        return state