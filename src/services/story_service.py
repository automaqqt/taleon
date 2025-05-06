# --- START OF FILE services/story_service.py ---

import os
import logging
import json
from dotenv import load_dotenv
import httpx
import re # Import re for placeholder finding
from typing import List, Dict, Any, Optional, Tuple

load_dotenv()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
SUMMARIZE_TURN_INTERVAL = 3 # Example value
MAX_HISTORY_FOR_PROMPT = 10

# Default values
DEFAULT_MODEL = os.getenv("DEFAULT_STORY_MODEL", "google/gemini-2.0-flash-exp:free")
DEFAULT_TEMPERATURE = 0.7

# API URLs and Keys
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Removed: VALID_STORY_CONFIG_KEYS

class StoryService:
    def __init__(self, api_key=None, api_url=None, model=None):
        """Initialize the story service with optional custom API settings"""
        self.openrouter_api_key = api_key or OPENROUTER_API_KEY
        self.openrouter_api_url = api_url or OPENROUTER_API_URL
        self.default_model = model or DEFAULT_MODEL

        if not self.openrouter_api_key:
            logger.warning("No OpenRouter API key provided. Story generation API calls may fail.")

    def _format_value_for_prompt(self, key: str, value: Any) -> str:
        """Formats specific story config values for insertion into the prompt."""
        if value is None:
            return "[Not Specified]"
        if isinstance(value, bool):
            return str(value) # "True" or "False"
        if isinstance(value, (int, float)):
            return str(value)

        # Specific formatting for complex types (lists, dicts)
        if key == "side_characters" and isinstance(value, list):
            formatted_chars = []
            for char in value:
                if isinstance(char, dict):
                    parts = [char.get('name', 'Unnamed Character')]
                    if char.get('trait'): parts.append(f"Trait: {char['trait']}")
                    if char.get('wish'): parts.append(f"Wish: {char['wish']}")
                    if len(parts) > 1:
                        formatted_chars.append(f"{parts[0]} ({', '.join(parts[1:])})")
                    else:
                        formatted_chars.append(parts[0])
                elif isinstance(char, str): # Handle list of strings
                     formatted_chars.append(char)
            return "Side characters: " + ", ".join(formatted_chars) if formatted_chars else "[No side characters specified]"

        elif key == "magic_elements" and isinstance(value, list):
            return "Magical elements involved: " + ", ".join(map(str, value)) if value else "[No magic elements specified]"

        elif key == "last_choices" and isinstance(value, list):
            return "Previous choices offered: " + ", ".join(map(str, value)) if value else "[No previous choices recorded]"

        elif isinstance(value, list):
            # Generic list formatting
            return f"{key}: " + ", ".join(map(str, value)) if value else f"[{key} not specified or empty]"
        elif isinstance(value, dict):
             # Generic dict formatting (simple key-value pairs)
             items = [f"{k}: {v}" for k, v in value.items()]
             return f"{key}: " + "; ".join(items) if items else f"[{key} not specified or empty]"
        else:
            # Default: convert to string
            return str(value)

    def _inject_context_into_prompt(
        self,
        system_prompt: str,
        user_story_context: Dict[str, Any],
        base_story_elements: Dict[str, Any],
        current_summary: str,
        original_tale_context: str,
        other_fields: Dict[str, Any] # e.g., {"current_turn_number": 5, "language": "German"}
    ) -> str:
        """
        Replaces placeholders in the system prompt with values from various context sources.
        Priority: other_fields > user_story_context > base_story_elements > special_cases.
        """
        formatted_prompt = system_prompt
        placeholders = re.findall(r"\{([^}]+)\}", formatted_prompt)
        found_keys = set() # Keep track of keys already replaced

        logger.debug(f"Injecting context. Placeholders found: {placeholders}")
        logger.debug(f"Context sources: other_fields={other_fields.keys()}, user_story_context={user_story_context.keys()}, base_story_elements={base_story_elements.keys()}")

        for placeholder in placeholders:
            if placeholder in found_keys:
                continue # Skip if already replaced by higher priority source

            value = None
            source = None

            # 1. Check other_fields (highest priority)
            if placeholder in other_fields:
                value = other_fields[placeholder]
                source = "other_fields"

            # 2. Check user_story_context (dynamic context)
            elif user_story_context and placeholder in user_story_context:
                value = user_story_context[placeholder]
                source = "user_story_context"

            # 3. Check base_story_elements (initial context)
            elif base_story_elements and placeholder in base_story_elements:
                value = base_story_elements[placeholder]
                source = "base_story_elements"

            # 4. Check special cases
            elif placeholder == "current_summary":
                value = current_summary
                source = "special_case"
            elif placeholder == "original_tale_context":
                value = original_tale_context
                source = "special_case"

            # Replace if value found
            if source:
                formatted_value = self._format_value_for_prompt(placeholder, value)
                formatted_prompt = formatted_prompt.replace(f"{{{placeholder}}}", formatted_value)
                found_keys.add(placeholder)
                logger.debug(f"Replaced {{{placeholder}}} with value from {source}.")
            else:
                logger.warning(f"Placeholder {{{placeholder}}} in prompt was not found in any context source. Leaving it unchanged.")

        logger.debug(f"Prompt after injection:\n{formatted_prompt[:500]}...") # Log start of final prompt
        return formatted_prompt

    async def generate_story_segment(
        self,
        # system_prompt argument is now the fully injected prompt
        injected_system_prompt: str,
        history: List[str], # This is just the text content list
        model: str = None,
        temperature: float = DEFAULT_TEMPERATURE
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Generate the next story segment using the prepared system prompt and history.
        """
        model_to_use = model or self.default_model

        # Prepare the history for the prompt - use most recent interactions
        prompt_history_content = history[-MAX_HISTORY_FOR_PROMPT:]

        # Format user prompt with the history
        user_prompt = f"""Recent Interaction History:
{'[Start of History]' if len(history) <= MAX_HISTORY_FOR_PROMPT else '[Last interactions]: '}
{chr(10).join(prompt_history_content)}

(The user's most recent action is the last message in the history above)

Your JSON Response:"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openrouter_api_key}"
            }

            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": injected_system_prompt}, # Use the fully prepared prompt
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"}, # Request JSON output
                "max_tokens": 2000 # Adjust as needed
            }

            logger.info(f"Generating story segment using model: {model_to_use}")
            # Avoid logging the full prompt here as it can be very large and sensitive
            logger.debug(f"API Payload (excluding messages): { {k:v for k,v in payload.items() if k != 'messages'} }")

            async with httpx.AsyncClient(timeout=460.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status() # Check for HTTP errors

                data = response.json()
                if not data.get("choices"):
                    logger.error(f"No 'choices' field in API response from {model_to_use}. Response: {data}")
                    return None, str(data)

                message_content = data["choices"][0].get("message", {}).get("content")
                if not message_content:
                     logger.error(f"Empty 'content' in API response choice from {model_to_use}. Response: {data}")
                     return None, str(data)

                raw_response_text = message_content # Keep the raw text

                # Attempt to parse the JSON content
                try:
                    # LLM might still wrap JSON in markdown, find it first
                    json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
                    json_match = re.search(json_pattern, message_content)
                    json_str_to_parse = message_content # Assume direct JSON by default

                    if json_match:
                        json_str_to_parse = json_match.group(1).strip()
                        logger.debug("Extracted JSON content from markdown block.")
                    else:
                         # Fallback: Find first '{' and last '}' if no markdown found
                         json_start = message_content.find('{')
                         json_end = message_content.rfind('}') + 1
                         if json_start != -1 and json_end != -1 and json_end > json_start:
                             json_str_to_parse = message_content[json_start:json_end]
                             logger.debug("Extracted JSON content using boundaries '{}'.")
                         else:
                             logger.warning("Could not find JSON markers (markdown or boundaries), attempting direct parse.")


                    parsed_data = json.loads(json_str_to_parse)

                    # Basic validation of expected structure
                    if (isinstance(parsed_data, dict) and
                        "storySegment" in parsed_data and isinstance(parsed_data["storySegment"], str) and
                        "choices" in parsed_data and isinstance(parsed_data["choices"], list) and
                        len(parsed_data["choices"]) >= 1): # Allow 1 choice minimum? Or require 2? Let's stick to >= 2 for now.

                        if len(parsed_data["choices"]) < 2:
                             logger.warning(f"Parsed JSON has fewer than 2 choices: {parsed_data['choices']}")
                             # Decide: return anyway or fail? Let's return but log.

                        logger.info("Successfully generated and parsed story segment JSON.")
                        return parsed_data, raw_response_text
                    else:
                        logger.error(f"Parsed JSON has invalid structure: {parsed_data}")
                        return None, raw_response_text

                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse LLM response as JSON: {json_err}. Raw response: {raw_response_text}")
                    return None, raw_response_text

        except httpx.HTTPStatusError as e:
            # Log specific HTTP errors
            error_body = e.response.text
            logger.error(f"HTTP error during story generation: {e.response.status_code} - {error_body[:500]}") # Log start of error body
            return None, f"API Error: {e.response.status_code}, {error_body}"
        except httpx.RequestError as e:
            # Log connection errors, timeouts etc.
            logger.error(f"Request error during story generation: {e}")
            return None, f"Network/Request Error: {e}"
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error during story generation: {str(e)}") # Use exception to log traceback
            return None, f"Unexpected Server Error: {str(e)}"

    def should_trigger_summary(self, turn_number: int) -> bool:
        """Check if this turn should trigger a summary update"""
        # Turn numbers usually start from 0 internally for the *request*,
        # but the *state* increments *after* generation.
        # If a segment for turn 0 was just generated, state is now 1.
        # Let's assume turn_number passed here is the *current state* before generating the *next* one.
        # So, trigger summary after turn 5, 10, 15 etc. are completed.
        # This means checking the turn number *before* incrementing it.
        current_turn_completed = turn_number
        return current_turn_completed > 0 and current_turn_completed % SUMMARIZE_TURN_INTERVAL == 0

    def format_user_action(self, action: Dict[str, Any]) -> str:
        """Format a user action into a text representation for history"""
        if action.get("choice"): # Use .get for safety
            return f"My choice: {action['choice']}"
        elif action.get("customInput"):
            return f"My custom action: {action['customInput']}"
        else:
            logger.warning(f"Formatting an action with unexpected structure: {action}")
            return "[[No valid action provided]]" # Clearer indication of error

# --- END OF FILE services/story_service.py ---