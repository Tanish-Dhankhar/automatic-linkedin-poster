"""
Utility functions for nodes - common functionality used across multiple nodes.
"""

import json
import re
from typing import Any, Dict, Optional


def parse_llm_json_response(response_text: str, fallback_value: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Robustly parse JSON from LLM response, handling common formatting issues.
    
    Args:
        response_text: Raw response text from LLM
        fallback_value: Value to return if parsing fails (defaults to empty dict)
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        json.JSONDecodeError: If parsing fails and no fallback provided
    """
    if fallback_value is None:
        fallback_value = {}
    
    # Clean up the response text
    cleaned_text = response_text.strip()
    
    # Remove markdown code blocks if present
    if "```json" in cleaned_text:
        # Extract content between ```json and ```
        json_match = re.search(r'```json\s*\n?(.*?)\n?```', cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(1).strip()
    elif "```" in cleaned_text:
        # Extract content between ``` blocks
        json_match = re.search(r'```\s*\n?(.*?)\n?```', cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(1).strip()
    
    # Remove any leading/trailing text that isn't JSON
    # Look for the first { and last }
    first_brace = cleaned_text.find('{')
    last_brace = cleaned_text.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned_text = cleaned_text[first_brace:last_brace + 1]
    
    # Try to parse the cleaned JSON
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        # Try some common fixes
        try:
            # Fix common issues like trailing commas, single quotes, etc.
            fixed_text = fix_common_json_issues(cleaned_text)
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            # If we have a fallback, use it
            if fallback_value is not None:
                print(f"⚠️ JSON parsing failed, using fallback value. Error: {e}")
                return fallback_value
            else:
                # Re-raise the original error
                raise e


def fix_common_json_issues(json_text: str) -> str:
    """
    Fix common JSON formatting issues that LLMs sometimes produce.
    
    Args:
        json_text: Potentially malformed JSON string
        
    Returns:
        Fixed JSON string
    """
    # Remove trailing commas before closing braces/brackets
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
    
    # Replace single quotes with double quotes (but not inside strings)
    # This is a simple approach - more complex scenarios might need a proper parser
    json_text = re.sub(r"'([^']*)':", r'"\1":', json_text)  # Keys
    json_text = re.sub(r":\s*'([^']*)'", r': "\1"', json_text)  # String values
    
    # Fix common boolean/null values
    json_text = re.sub(r'\bTrue\b', 'true', json_text)
    json_text = re.sub(r'\bFalse\b', 'false', json_text)
    json_text = re.sub(r'\bNone\b', 'null', json_text)
    
    return json_text


def safe_get_nested_value(data: Dict[str, Any], keys: str, default: Any = None) -> Any:
    """
    Safely get a nested dictionary value using dot notation.
    
    Args:
        data: Dictionary to search
        keys: Dot-separated key path (e.g., "user.profile.name")
        default: Value to return if key not found
        
    Returns:
        The found value or default
        
    Example:
        safe_get_nested_value({"user": {"name": "John"}}, "user.name") -> "John"
        safe_get_nested_value({"user": {"name": "John"}}, "user.age", 0) -> 0
    """
    try:
        current = data
        for key in keys.split('.'):
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default


def validate_required_fields(data: Dict[str, Any], required_fields: list) -> tuple[bool, list]:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names (can use dot notation)
        
    Returns:
        Tuple of (is_valid, missing_fields)
    """
    missing_fields = []
    
    for field in required_fields:
        if '.' in field:
            # Handle nested fields
            value = safe_get_nested_value(data, field)
            if value is None:
                missing_fields.append(field)
        else:
            # Handle top-level fields
            if field not in data or data[field] is None:
                missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields
