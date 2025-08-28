"""
Update Persona Node - Final Stage: Automatically updates persona.json with new information.
Intelligently parses user's post content and updates relevant sections of the persona file.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import sys
sys.path.append('..')
from state import WorkflowState
from credentials_loader import get_persona_path
from .utils import parse_llm_json_response

load_dotenv()


def update_persona_from_post(state: WorkflowState) -> WorkflowState:
    """
    Uses LLM to intelligently extract new information from the user's post
    and update the persona.json file with relevant achievements, skills, experiences, etc.
    
    Args:
        state: Current workflow state with completed post
        
    Returns:
        Updated state with persona update information
    """
    print("\n" + "-"*40)
    print("📈 Final Stage: Auto-Updating Persona")
    print("-"*40)
    
    try:
        # Check for errors or if post wasn't saved
        if state.get('error') or not state.get('saved_to_sheet'):
            print("⏭️ Skipping persona update (post not saved successfully)")
            return state
        
        # Load current persona using credentials_loader
        persona_path = get_persona_path()
        with open(persona_path, 'r', encoding='utf-8') as f:
            current_persona = json.load(f)
        
        # Initialize Gemini Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.3,  # Lower temperature for precise extraction
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Get the user's original input and structured data
        raw_input = state.get('raw_input', '')
        post_metadata = state.get('post_metadata', {})
        event_details = state.get('event_details', {})
        
        # Create comprehensive analysis prompt
        system_prompt = f"""You are a persona management expert that analyzes user content and extracts valuable information to update their professional persona.

        Your task is to analyze the user's input about their professional activities and identify new information that should be added to their persona file.

        PERSONA SECTIONS TO CONSIDER UPDATING:

        1. **ACHIEVEMENTS** - Awards, recognitions, competitions won, certifications earned
        2. **EXPERIENCES** - New projects, roles, responsibilities, collaborations
        3. **SKILLS** - New technical skills, tools, technologies, soft skills learned
        4. **EDUCATION** - Courses completed, degrees, training programs
        5. **INTERESTS** - New professional interests or focus areas discovered
        6. **VALUES** - New values or principles demonstrated through actions
        7. **GOALS** - Updated career goals or aspirations mentioned
        8. **NETWORK** - New types of people or communities engaged with

        EXTRACTION RULES:
        - Only extract information that is NEW or represents GROWTH/CHANGE
        - Don't duplicate existing information
        - Be specific and concrete - avoid generic descriptions  
        - Focus on professional development and career-relevant information
        - Include dates when mentioned
        - Extract measurable results and impacts when available

        OUTPUT FORMAT:
        Return a JSON object with updates for each relevant section. Use null for sections with no new information.

        Example structure:
        {{
            "achievements": [
                {{
                    "title": "Hackathon Winner",
                    "organization": "TechCorp",
                    "date": "2025-08",
                    "description": "Won first place in AI/ML category"
                }}
            ],
            "experiences": [
                {{
                    "type": "project",
                    "title": "ML Prediction Model",
                    "date": "2025-08",
                    "description": "Improved prediction accuracy by 23% using TensorFlow",
                    "impact": "23% accuracy improvement",
                    "technologies": ["TensorFlow", "AWS"]
                }}
            ],
            "skills": {{
                "technical_skills": ["New Technology", "Tool Name"],
                "soft_skills": ["Leadership", "Public Speaking"]
            }},
            "education": null,
            "interests": null,
            "values": null,
            "goals": null,
            "network_updates": null
        }}

        Be conservative - only add information that clearly represents new professional development."""

        # Prepare analysis context
        analysis_context = {
            "raw_user_input": raw_input,
            "event_type": post_metadata.get('event_type'),
            "event_details": {
                "description": event_details.get('description'),
                "role": event_details.get('role'), 
                "tools_skills": event_details.get('tools_skills', []),
                "challenges": event_details.get('challenges'),
                "learnings": event_details.get('learnings'),
                "outcome": event_details.get('outcome'),
                "acknowledgements": event_details.get('acknowledgements', [])
            },
            "current_persona_sections": {
                "existing_skills": current_persona.get('skills_expertise', {}).get('technical_skills', []),
                "existing_achievements": [exp.get('title', '') for exp in current_persona.get('background', {}).get('achievements', [])],
                "current_interests": current_persona.get('interests', [])
            }
        }

        user_message = f"""Analyze this professional activity and extract new information for persona updates:

        USER INPUT:
        {raw_input}

        STRUCTURED EVENT DATA:
        {json.dumps(analysis_context['event_details'], indent=2)}

        EVENT TYPE: {analysis_context['event_type']}

        CURRENT PERSONA CONTEXT (to avoid duplicates):
        {json.dumps(analysis_context['current_persona_sections'], indent=2)}

        Extract only genuinely NEW information that represents professional growth or development.
        Return the extraction results in the specified JSON format."""

        # Get extraction results
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        print("🔍 Analyzing content for persona updates...")
        response = llm.invoke(messages)

        # Parse the extraction results using robust utility function
        fallback_updates = {
            "achievements": None,
            "experiences": None,
            "skills": None,
            "education": None,
            "interests": None,
            "values": None,
            "goals": None,
            "network_updates": None
        }
        extracted_updates = parse_llm_json_response(response.content, fallback_updates)

        # Apply updates to persona
        updated_persona = apply_persona_updates(current_persona, extracted_updates)
        
        # Save updated persona if there were changes
        changes_made = has_persona_changes(current_persona, updated_persona)
        
        if changes_made:
            # Create backup of current persona
            backup_path = f"{persona_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(backup_path, 'w') as f:
                json.dump(current_persona, f, indent=2)
            
            # Save updated persona
            with open(persona_path, 'w') as f:
                json.dump(updated_persona, f, indent=2)
            
            # Track updates in state
            state['persona_updated'] = True
            state['persona_updates'] = extracted_updates
            state['persona_backup_path'] = backup_path
            
            # Display summary
            update_summary = generate_update_summary(extracted_updates)
            print(f"\n✅ Persona updated successfully!")
            print(f"   • Backup saved: {os.path.basename(backup_path)}")
            print(f"   • Updates made: {len(update_summary)} section(s)")
            
            for section, items in update_summary.items():
                if items:
                    print(f"   • {section}: {len(items)} new item(s)")
            
        else:
            print("\n📋 No new information found to add to persona")
            state['persona_updated'] = False
            state['persona_updates'] = {}

        return state

    except Exception as e:
        state['error'] = f"Error updating persona: {str(e)}"
        state['error_node'] = "update_persona"
        print(f"❌ Error: {str(e)}")
        return state


def apply_persona_updates(current_persona: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply the extracted updates to the persona structure.
    
    Args:
        current_persona: Current persona data
        updates: New information to add
        
    Returns:
        Updated persona data
    """
    updated_persona = current_persona.copy()
    
    # Update achievements
    if updates.get('achievements'):
        if 'background' not in updated_persona:
            updated_persona['background'] = {}
        if 'achievements' not in updated_persona['background']:
            updated_persona['background']['achievements'] = []
        
        for achievement in updates['achievements']:
            # Check if achievement already exists
            existing_titles = [a.get('title', '').lower() for a in updated_persona['background']['achievements']]
            if achievement['title'].lower() not in existing_titles:
                updated_persona['background']['achievements'].append(achievement)

    # Update experiences
    if updates.get('experiences'):
        if 'background' not in updated_persona:
            updated_persona['background'] = {}
        if 'recent_projects' not in updated_persona['background']:
            updated_persona['background']['recent_projects'] = []
        
        for experience in updates['experiences']:
            # Add with timestamp to avoid duplicates
            experience['added_date'] = datetime.now().strftime('%Y-%m-%d')
            updated_persona['background']['recent_projects'].append(experience)

    # Update skills
    if updates.get('skills'):
        if 'skills_expertise' not in updated_persona:
            updated_persona['skills_expertise'] = {'technical_skills': [], 'soft_skills': []}
        
        # Add technical skills
        if updates['skills'].get('technical_skills'):
            existing_tech = [s.lower() for s in updated_persona['skills_expertise'].get('technical_skills', [])]
            for skill in updates['skills']['technical_skills']:
                if skill.lower() not in existing_tech:
                    updated_persona['skills_expertise']['technical_skills'].append(skill)
        
        # Add soft skills
        if updates['skills'].get('soft_skills'):
            existing_soft = [s.lower() for s in updated_persona['skills_expertise'].get('soft_skills', [])]
            for skill in updates['skills']['soft_skills']:
                if skill.lower() not in existing_soft:
                    updated_persona['skills_expertise']['soft_skills'].append(skill)

    # Update education
    if updates.get('education'):
        if 'background' not in updated_persona:
            updated_persona['background'] = {}
        if 'education' not in updated_persona['background']:
            updated_persona['background']['education'] = []
        
        # Handle both list and dict formats
        education_items = updates['education'] if isinstance(updates['education'], list) else [updates['education']]
        for edu in education_items:
            if edu:  # Skip None/empty items
                updated_persona['background']['education'].append(edu)

    # Update interests
    if updates.get('interests'):
        if 'interests' not in updated_persona:
            updated_persona['interests'] = []
        
        # Handle both list and string formats
        interest_items = updates['interests'] if isinstance(updates['interests'], list) else [updates['interests']]
        existing_interests = [i.lower() for i in updated_persona['interests']]
        for interest in interest_items:
            if interest and interest.lower() not in existing_interests:
                updated_persona['interests'].append(interest)

    # Update values
    if updates.get('values'):
        if 'professional_goals' not in updated_persona:
            updated_persona['professional_goals'] = {}
        if 'values' not in updated_persona['professional_goals']:
            updated_persona['professional_goals']['values'] = []
        
        # Handle both list and string formats
        value_items = updates['values'] if isinstance(updates['values'], list) else [updates['values']]
        existing_values = [v.lower() for v in updated_persona['professional_goals']['values']]
        for value in value_items:
            if value and value.lower() not in existing_values:
                updated_persona['professional_goals']['values'].append(value)

    # Update goals
    if updates.get('goals'):
        if 'professional_goals' not in updated_persona:
            updated_persona['professional_goals'] = {}
        
        # Handle both dict and list formats
        if isinstance(updates['goals'], dict):
            for goal_type, goal_value in updates['goals'].items():
                updated_persona['professional_goals'][goal_type] = goal_value
        elif isinstance(updates['goals'], list):
            # If it's a list, add them as a goals list
            if 'goals' not in updated_persona['professional_goals']:
                updated_persona['professional_goals']['goals'] = []
            for goal in updates['goals']:
                if goal and goal not in updated_persona['professional_goals']['goals']:
                    updated_persona['professional_goals']['goals'].append(goal)

    # Update network information
    if updates.get('network_updates'):
        if 'network_context' not in updated_persona:
            updated_persona['network_context'] = {'target_audience': [], 'industry_communities': []}
        
        if updates['network_updates'].get('new_communities'):
            existing_communities = [c.lower() for c in updated_persona['network_context'].get('industry_communities', [])]
            for community in updates['network_updates']['new_communities']:
                if community.lower() not in existing_communities:
                    updated_persona['network_context']['industry_communities'].append(community)

    return updated_persona


def has_persona_changes(original: Dict[str, Any], updated: Dict[str, Any]) -> bool:
    """
    Check if there are actual changes between original and updated persona.
    
    Args:
        original: Original persona data
        updated: Updated persona data
        
    Returns:
        True if changes were made, False otherwise
    """
    return json.dumps(original, sort_keys=True) != json.dumps(updated, sort_keys=True)


def generate_update_summary(updates: Dict[str, Any]) -> Dict[str, List]:
    """
    Generate a summary of what was updated.
    
    Args:
        updates: Dictionary of updates made
        
    Returns:
        Summary dictionary
    """
    summary = {}
    
    if updates.get('achievements'):
        summary['achievements'] = [a['title'] for a in updates['achievements']]
    
    if updates.get('experiences'):
        summary['experiences'] = [e['title'] for e in updates['experiences']]
    
    if updates.get('skills'):
        skills_list = []
        if updates['skills'].get('technical_skills'):
            skills_list.extend(updates['skills']['technical_skills'])
        if updates['skills'].get('soft_skills'):
            skills_list.extend(updates['skills']['soft_skills'])
        if skills_list:
            summary['skills'] = skills_list
    
    if updates.get('education'):
        education_items = updates['education'] if isinstance(updates['education'], list) else [updates['education']]
        summary['education'] = [e.get('degree', e.get('title', 'New Education')) if isinstance(e, dict) else str(e) for e in education_items if e]
    
    if updates.get('interests'):
        summary['interests'] = updates['interests'] if isinstance(updates['interests'], list) else [updates['interests']]
    
    if updates.get('values'):
        summary['values'] = updates['values'] if isinstance(updates['values'], list) else [updates['values']]
    
    return summary


def rollback_persona_update(backup_path: str, persona_path: str) -> bool:
    """
    Rollback persona to a previous backup.
    
    Args:
        backup_path: Path to backup file
        persona_path: Path to current persona file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(backup_path):
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            with open(persona_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            return True
        return False
    except Exception:
        return False
