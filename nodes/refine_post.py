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
        system_prompt = f"""You are an expert LinkedIn content strategist specializing in humanizing and refining professional posts. 
        Your job is to take a good LinkedIn post and make it EXCEPTIONAL by adding human touches, authenticity, and engagement.

        REFINEMENT OBJECTIVES:
        1. HUMANIZE: Add personal touches, vulnerability, and authentic voice
        2. ENHANCE ENGAGEMENT: Improve hooks, storytelling, and calls-to-action  
        3. OPTIMIZE FLOW: Perfect the narrative structure and readability
        4. ADD AUTHENTICITY: Include genuine emotions, lessons learned, and personal insights
        5. MAINTAIN PROFESSIONALISM: Keep it appropriate for LinkedIn while being human

        HUMANIZATION TECHNIQUES:
        - Add genuine emotions and personal reactions
        - Include specific, relatable details that paint a picture
        - Use conversational language while staying professional
        - Add moments of vulnerability or learning
        - Include authentic insights and reflections
        - Use power words that create emotional connection

        ENGAGEMENT OPTIMIZATION:
        - Strengthen the opening hook (first 1-2 lines are crucial)
        - Improve storytelling flow with clear narrative arc
        - Add sensory details and specific examples
        - Enhance the call-to-action or question
        - Optimize for LinkedIn algorithm (engagement-driving content)
        - Add strategic line breaks for mobile readability

        AUTHENTICITY MARKERS:
        - Personal pronouns and first-person perspective
        - Specific numbers, dates, and concrete details
        - Lessons learned and growth mindset language
        - Acknowledgment of challenges or failures
        - Genuine gratitude and recognition of others
        - Future-focused optimism balanced with realism

        STRUCTURE OPTIMIZATION:
        - Hook (grab attention immediately)
        - Context (brief setup)
        - Story/Experience (the main content with details)
        - Insight/Learning (what it means)
        - Connection/CTA (engage the audience)

        STYLE GUIDELINES:
        - Tone: {persona_context.get('tone', 'authentic and professional')}
        - Writing Style: More conversational and human than the original
        - Emoji Usage: {comm_prefs.get('emoji_frequency', 'moderate')} - use strategically for emphasis
        - Length: Keep within LinkedIn's optimal range (150-300 words)
        - Paragraph Length: Short paragraphs (2-3 lines max) for mobile reading

        Do NOT:
        - Change the core message or facts
        - Add false information or exaggerate claims
        - Make it overly casual or unprofessional
        - Use generic corporate speak or buzzwords
        - Copy exact phrases from the original if they can be improved

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

        user_message = f"""Please refine and humanize this LinkedIn post:

        ORIGINAL POST:
        {draft_post}

        CONTEXT FOR REFINEMENT:
        {json.dumps(refinement_context, indent=2)}

        FOCUS AREAS FOR THIS POST:
        - Make it more authentic and personal
        - Improve the emotional connection with readers
        - Enhance the storytelling elements
        - Optimize for LinkedIn engagement
        - Add specific, relatable details
        - Strengthen the hook and call-to-action

        Transform this into a post that feels genuinely human while maintaining professionalism and the core message."""

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
