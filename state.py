"""
State management for the LinkedIn Post Creation workflow.
Defines the state schema that will be passed between nodes in the LangGraph.
"""

from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime


class PostMetadata(TypedDict):
    """Metadata about the post event/content."""
    event_type: Optional[str]  # project | hackathon | internship | competition | achievement | learning | experience | collaboration | talk/event
    title_hook: Optional[str]  # optional catchy first line
    date_of_event: Optional[str]  # optional, e.g., "2025-08-16"


class EventDetails(TypedDict):
    """Detailed information about the event/content."""
    description: Optional[str]  # context of what happened
    role: Optional[str]  # what the user specifically did
    tools_skills: Optional[List[str]]  # technologies/skills used
    challenges: Optional[str]  # problems faced and solutions
    learnings: Optional[str]  # key personal takeaways
    outcome: Optional[str]  # results, recognition, usefulness
    acknowledgements: Optional[List[str]]  # people/orgs to thank or tag
    engagement_question: Optional[str]  # question to drive interaction
    attachments: Optional[List[str]]  # media paths/URLs


class PersonaContext(TypedDict):
    """Persona enrichment data."""
    tone: Optional[str]  # writing tone from persona
    relevant_experience: Optional[str]  # relevant background
    career_goal_alignment: Optional[str]  # how this aligns with goals


class WorkflowState(TypedDict):
    """Main state object passed between nodes in the workflow."""
    # User input
    raw_input: Optional[str]  # Original rough notes from user
    media_paths: Optional[List[str]]  # Attachment paths
    scheduled_time: Optional[str]  # When to post (YYYY-MM-DD HH:MM)
    
    # Structured data
    post_metadata: Optional[PostMetadata]
    event_details: Optional[EventDetails]
    
    # Validation
    is_complete: Optional[bool]  # Whether info is complete
    missing_fields: Optional[List[str]]  # Fields that need more info
    clarifying_questions: Optional[List[str]]  # Questions to ask user
    user_responses: Optional[Dict[str, str]]  # Responses to clarifying questions
    
    # Persona enrichment
    persona_context: Optional[PersonaContext]
    persona_data: Optional[Dict[str, Any]]  # Full persona JSON
    
    # Generated content
    draft_post: Optional[str]  # Generated LinkedIn post
    refined_post: Optional[str]  # Humanized and refined post
    refinement_metadata: Optional[Dict[str, Any]]  # Refinement analysis data
    post_approved: Optional[bool]  # User approval status
    user_feedback: Optional[str]  # Feedback for revision
    revision_count: Optional[int]  # Number of revisions made
    
    # Final output
    final_post: Optional[str]  # Approved final post
    post_number: Optional[int]  # Sequential post ID for sheet
    saved_to_sheet: Optional[bool]  # Whether saved successfully
    
    # Persona auto-update
    persona_updated: Optional[bool]  # Whether persona was updated
    persona_updates: Optional[Dict[str, Any]]  # Details of persona updates made
    persona_backup_path: Optional[str]  # Path to persona backup file
    
    # Error handling
    error: Optional[str]  # Any error messages
    error_node: Optional[str]  # Which node had the error
