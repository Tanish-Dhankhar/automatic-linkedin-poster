"""
Refine Post Node - LLM Stage 5: Humanizes and refines the generated LinkedIn post.
Focuses on making content more authentic, engaging, and natural while maintaining professionalism.
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


def refine_and_humanize_post(state: WorkflowState) -> WorkflowState:
    """
    Uses Gemini Flash to refine and humanize the generated LinkedIn post.
    Focuses on making the content more authentic, engaging, and natural.
    
    Args:
        state: Current workflow state with draft post
        
    Returns:
        Updated state with refined post
    """
    print("\n" + "-"*40)
    print("🎨 LLM Stage 5: Refining & Humanizing Post")
    print("-"*40)
    
    try:
        # Check for errors
        if state.get('error'):
            return state
        
        # Initialize Gemini Flash with slightly higher temperature for creativity
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.8,  # Higher temperature for more creative refinement
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Get all relevant data
        draft_post = state.get('draft_post', '')
        post_metadata = state.get('post_metadata', {})
        event_details = state.get('event_details', {})
        persona_data = state.get('persona_data', {})
        persona_context = state.get('persona_context', {})
        
        # Extract communication preferences
        comm_prefs = persona_data.get('communication_preferences', {})
        
        # Create comprehensive refinement system prompt
        system_prompt = f"""You are a human LinkedIn user who writes incredibly engaging, authentic posts that feel genuinely personal. Your writing style is natural, conversational, and never sounds like AI-generated content.

        YOUR WRITING PHILOSOPHY:
        - Write like you're talking to a close colleague over coffee
        - Share real human experiences, not corporate narratives  
        - Be vulnerable and honest about challenges and failures
        - Use simple, everyday language instead of business jargon
        - Tell stories that people can see themselves in
        - Show genuine personality quirks and individual voice

        HUMAN WRITING PATTERNS TO FOLLOW:
        1. START WITH IMPACT: Open with a moment, realization, or surprising detail
        2. PAINT THE SCENE: Help readers visualize what happened with specific details
        3. SHARE THE STRUGGLE: Include the messy, uncomfortable, or challenging parts
        4. REVEAL THE INSIGHT: What you learned that others can relate to
        5. CONNECT AUTHENTICALLY: End with genuine curiosity about their experiences

        MAKE IT SOUND HUMAN BY:
        - Using contractions (I'm, don't, wasn't, can't)
        - Including hesitations and qualifiers (honestly, actually, I think, maybe)
        - Adding small imperfections (not everything went perfectly)
        - Using specific, random details that only a real person would notice
        - Mentioning emotions and physical sensations
        - Including timestamps and locations that feel real
        - Admitting when you don't know something
        - Using colloquial phrases people actually say

        AVOID AI-SOUNDING PHRASES:
        - "I'm excited to share"
        - "Key takeaways"
        - "Delighted to announce" 
        - "Thrilled to"
        - "Game-changing"
        - "Grateful for the opportunity"
        - "Looking forward to"
        - Perfect, polished narratives

        WRITE LIKE A REAL PERSON:
        - "So this happened yesterday..."
        - "I honestly didn't see this coming"
        - "Here's what I learned the hard way"
        - "Anyone else struggle with this?"
        - "I used to think... but now I realize..."
        - Include specific details like "3:47 AM" or "my third cup of coffee"

        AUTHENTICITY MARKERS:
        - Admit when things didn't go as planned
        - Share moments of doubt or confusion
        - Include what you were thinking/feeling in the moment
        - Mention other people's reactions
        - Add sensory details (what you saw, heard, felt)
        - Use parentheses for side thoughts (like real people do)
        - Include minor, relatable complaints or observations

        TONE: {persona_context.get('tone', 'conversational and genuine')}
        
        STRUCTURE FOR HUMAN POSTS:
        - Hook: A moment or realization that grabs attention
        - Story: What actually happened with real details
        - Struggle: The challenging or unexpected part
        - Learning: Your genuine takeaway or shift in thinking
        - Connection: A real question about their experiences

        FORMATTING RULES:
        - Short paragraphs (1-2 sentences max)
        - Use line breaks like people naturally pause when speaking
        - No bullet points or corporate formatting
        - Let thoughts flow naturally with transitions

        Remember: Real humans don't write perfect posts. They write posts that feel real, relatable, and like genuine human experiences. Make every word count toward building that authentic connection.

        Output ONLY the refined post content, nothing else."""

        # Prepare the refinement context
        refinement_context = {
            "original_post": draft_post,
            "event_type": post_metadata.get('event_type', 'experience'),
            "industry": persona_data.get('basic_info', {}).get('industry', 'Professional'),
            "author_style": persona_context.get('writing_style_notes', 'conversational'),
            "target_audience": persona_data.get('network_context', {}).get('target_audience', []),
            "values": persona_data.get('professional_goals', {}).get('values', []),
            "communication_preferences": comm_prefs
        }

        user_message = f"""Transform this LinkedIn post into something that feels genuinely human-written:

        ORIGINAL POST:
        {draft_post}

        CONTEXT:
        {json.dumps(refinement_context, indent=2)}

        YOUR TASK:
        Rewrite this as if you're a real person sharing a genuine experience. Make it feel like something an actual human would write - imperfect, authentic, and relatable. Include:

        1. A compelling opening moment (not "I'm excited to share...")
        2. Specific, visualizable details that paint the picture
        3. The messy or challenging parts (what really happened)
        4. Your genuine emotional reaction and learning
        5. A real question that invites authentic responses

        Write like you're telling this story to a friend, not delivering a corporate announcement. Make every sentence feel human and conversational."""

        # Get refinement response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        print("✨ Humanizing and refining your post...")
        response = llm.invoke(messages)

        # Extract the refined post
        refined_post = response.content.strip()

        # Store the refined post and metadata
        state['refined_post'] = refined_post
        state['draft_post'] = refined_post  # Update draft_post for approval process
        
        # Add refinement metadata
        refinement_metadata = {
            'original_length': len(draft_post.split()),
            'refined_length': len(refined_post.split()),
            'refinement_focus': [
                'humanization',
                'engagement_optimization', 
                'authenticity_enhancement',
                'flow_improvement'
            ],
            'changes_made': analyze_changes(draft_post, refined_post)
        }
        state['refinement_metadata'] = refinement_metadata

        # Calculate improvement metrics
        original_words = len(draft_post.split())
        refined_words = len(refined_post.split())
        
        print("\n✅ Post refined and humanized successfully!")
        print(f"   • Original length: {original_words} words")
        print(f"   • Refined length: {refined_words} words")
        print(f"   • Focus: Humanization + Engagement")
        
        # Show key improvements made
        improvements = refinement_metadata['changes_made']
        if improvements:
            print(f"   • Key improvements: {', '.join(improvements[:3])}")

        # Show preview comparison
        print(f"\n🔄 Refinement Preview:")
        print(f"   Original hook: {draft_post[:80]}...")
        refined_preview = refined_post[:80] + "..." if len(refined_post) > 80 else refined_post
        print(f"   Refined hook:  {refined_preview}")

        return state

    except Exception as e:
        state['error'] = f"Error in post refinement: {str(e)}"
        state['error_node'] = "refine_post"
        print(f"❌ Error: {str(e)}")
        return state


def analyze_changes(original: str, refined: str) -> list:
    """
    Analyze the key changes made during refinement.
    
    Args:
        original: Original post content
        refined: Refined post content
        
    Returns:
        List of improvement categories
    """
    improvements = []
    
    # Check for various improvements
    original_lower = original.lower()
    refined_lower = refined.lower()
    
    # Emotional words indicating humanization
    emotional_words = ['excited', 'grateful', 'proud', 'learned', 'realized', 'felt', 'discovered', 'struggled', 'achieved']
    if any(word in refined_lower and word not in original_lower for word in emotional_words):
        improvements.append('added_emotions')
    
    # Personal pronouns indicating more personal touch
    personal_pronouns = ['i\'m', 'i\'ve', 'my journey', 'personally', 'honestly']
    if any(phrase in refined_lower and phrase not in original_lower for phrase in personal_pronouns):
        improvements.append('more_personal')
    
    # Question marks indicating better engagement
    if refined.count('?') > original.count('?'):
        improvements.append('enhanced_engagement')
    
    # Line breaks indicating better formatting
    if refined.count('\n') > original.count('\n'):
        improvements.append('better_formatting')
    
    # Specific numbers or details
    import re
    original_numbers = len(re.findall(r'\d+', original))
    refined_numbers = len(re.findall(r'\d+', refined))
    if refined_numbers > original_numbers:
        improvements.append('added_specifics')
    
    # Hook improvement (first 50 characters significantly different)
    if original[:50].lower() != refined[:50].lower():
        improvements.append('improved_hook')
    
    # Length optimization
    original_words = len(original.split())
    refined_words = len(refined.split())
    if abs(refined_words - 200) < abs(original_words - 200):  # 200 is optimal LinkedIn length
        improvements.append('optimized_length')
    
    return improvements[:5]  # Return top 5 improvements


def get_refinement_suggestions(post_content: str, persona_data: dict) -> list:
    """
    Generate specific suggestions for post refinement.
    
    Args:
        post_content: The post content to analyze
        persona_data: User's persona data
        
    Returns:
        List of specific improvement suggestions
    """
    suggestions = []
    
    # Check post length
    word_count = len(post_content.split())
    if word_count < 100:
        suggestions.append("Consider adding more specific details or examples")
    elif word_count > 300:
        suggestions.append("Consider condensing for better mobile readability")
    
    # Check for questions/engagement
    if '?' not in post_content:
        suggestions.append("Add a question to encourage audience engagement")
    
    # Check for personal elements
    personal_words = ['i', 'my', 'me', 'personally']
    if not any(word in post_content.lower() for word in personal_words):
        suggestions.append("Add more personal touches to increase authenticity")
    
    # Check for specific details
    import re
    if len(re.findall(r'\d+', post_content)) < 2:
        suggestions.append("Include specific numbers or metrics where relevant")
    
    # Check for line breaks (mobile optimization)
    lines = post_content.split('\n')
    long_paragraphs = [line for line in lines if len(line) > 200]
    if long_paragraphs:
        suggestions.append("Break up long paragraphs for mobile readability")
    
    return suggestions