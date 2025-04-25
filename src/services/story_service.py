# --- START OF FILE story_service.py ---

import os
import logging
import json
from dotenv import load_dotenv
import httpx
import re # Import re for placeholder finding
from typing import List, Dict, Any, Optional, Tuple
load_dotenv()
# Setup logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Let's use DEBUG level to see the formatted prompt
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
SUMMARIZE_TURN_INTERVAL = 5
MAX_HISTORY_FOR_PROMPT = 10
MAX_HISTORY_FOR_RAG_QUERY = 6

# Default values
DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"
DEFAULT_TEMPERATURE = 0.7

# API URLs
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Define valid story config keys that can be injected
VALID_STORY_CONFIG_KEYS = {
    "main_character",
    "main_character_trait",
    "main_character_wish",
    "side_characters",
    "initial_task",
    "magic_elements",
    "obstacle",
    "reward",
    "cliffhanger_situation",
    "setting",
    # Also include existing dynamic placeholders
    "current_summary",
    "original_tale_context"
}

class StoryService:
    def __init__(self, api_key=None, api_url=None, model=None):
        """Initialize the story service with optional custom API settings"""
        self.openrouter_api_key = api_key or OPENROUTER_API_KEY
        self.openrouter_api_url = api_url or OPENROUTER_API_URL
        self.default_model = model or DEFAULT_MODEL

        if not self.openrouter_api_key:
            logger.warning("No OpenRouter API key provided. API calls will fail.")

    def _format_value_for_prompt(self, key: str, value: Any) -> str:
        """Formats specific story config values for insertion into the prompt."""
        if value is None:
            return "[Not Specified]"

        if key == "side_characters":
            if isinstance(value, list) and value:
                # Assuming value is a list of dicts like [{'name': 'x', 'trait': 'y', 'wish': 'z'}, ...]
                formatted_chars = []
                for char in value:
                    if isinstance(char, dict):
                        parts = [char.get('name', 'Unnamed Character')]
                        if char.get('trait'): parts.append(f"Trait: {char['trait']}")
                        if char.get('wish'): parts.append(f"Wish: {char['wish']}")
                        # Join parts, putting trait/wish in parentheses if they exist
                        if len(parts) > 1:
                           formatted_chars.append(f"{parts[0]} ({', '.join(parts[1:])})")
                        else:
                            formatted_chars.append(parts[0])
                    else: # Fallback if it's not a list of dicts
                        formatted_chars.append(str(char))
                return "Side characters: " + ", ".join(formatted_chars) if formatted_chars else "[No side characters specified]"
            else:
                return "[No side characters specified]"
        elif key == "magic_elements":
            if isinstance(value, list) and value:
                # Assuming value is a list of strings
                return "Magical elements involved: " + ", ".join(map(str, value))
            else:
                return "[No magic elements specified]"
        else:
            # Default: convert to string
            return str(value)

    def _inject_context_into_prompt(
        self,
        system_prompt: str,
        story_config: Dict[str, Any],
        current_summary: str,
        original_tale_context: str
    ) -> str:
        """Replaces placeholders in the system prompt with values from story_config."""
        formatted_prompt = system_prompt

        # Combine static story config with dynamic context for replacement
        context_data = story_config.copy()
        context_data["current_summary"] = current_summary
        context_data["original_tale_context"] = original_tale_context

        # Find all placeholders like {key}
        placeholders = re.findall(r"\{([^}]+)\}", formatted_prompt)

        for placeholder in placeholders:
            if placeholder in VALID_STORY_CONFIG_KEYS:
                value = context_data.get(placeholder)
                formatted_value = self._format_value_for_prompt(placeholder, value)
                formatted_prompt = formatted_prompt.replace(f"{{{placeholder}}}", formatted_value)
            else:
                logger.warning(f"Found placeholder {{{placeholder}}} in prompt, but it's not a valid or known key. Leaving it unchanged.")

        return formatted_prompt


    async def generate_story_segment(
        self,
        system_prompt: str,
        history: List[str],
        current_summary: str,
        original_tale_context: str,
        story_config: Dict[str, Any], # <-- New parameter for user story data
        model: str = None,
        temperature: float = DEFAULT_TEMPERATURE
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Generate the next story segment based on history and context.

        Args:
            system_prompt: Base system prompt potentially containing placeholders like {main_character}.
            history: List of previous message strings in the conversation.
            current_summary: Current summary of the story state.
            original_tale_context: Original tale context for reference.
            story_config: Dictionary containing user-specific story details (main character, etc.).
            model: Optional model override.
            temperature: Temperature setting for the LLM (0-1).

        Returns:
            Tuple containing (parsed response as dict, raw LLM response text)
        """
        model_to_use = model or self.default_model

        # Prepare the history for the prompt - use most recent interactions
        if len(history) == 1:
            prompt_history = current_summary
        else:
            prompt_history = history[-MAX_HISTORY_FOR_PROMPT:] if len(history) > MAX_HISTORY_FOR_PROMPT else history
        # Format user prompt with the history
        user_prompt = f"""Recent Interaction History:
{'[Start of History]' if len(history) <= MAX_HISTORY_FOR_PROMPT else '[... earlier history summarized ...]'}
{prompt_history if len(history) == 1 else chr(10).join(prompt_history) }

(The user's most recent action is the last message in the history above)

Your JSON Response:"""

        # Inject context into the system prompt
        try:
            formatted_system_prompt = self._inject_context_into_prompt(
                system_prompt,
                story_config,
                current_summary,
                original_tale_context
            )
            logger.debug(f"Final System Prompt after injection:\n{formatted_system_prompt}") # Log the final prompt
        except Exception as e:
            logger.error(f"Failed to inject context into system prompt: {e}")
            # Fallback to original prompt to potentially allow partial continuation
            formatted_system_prompt = system_prompt.replace("{current_summary}", current_summary or "[No Summary Yet]")
            formatted_system_prompt = formatted_system_prompt.replace("{original_tale_context}", original_tale_context or "[No Original Tale Context]")


        # Make the API call
        print(user_prompt)
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openrouter_api_key}"
            }

            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": formatted_system_prompt}, # Use the formatted prompt
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "max_tokens": 2000
            }

            logger.info(f"Generating story segment using model: {model_to_use}")
            logger.debug(f"API Payload (excluding messages for brevity): { {k:v for k,v in payload.items() if k != 'messages'} }")


            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()
                if "choices" not in data or not data["choices"]:
                    logger.error("No choices in API response")
                    return None, str(data)

                raw_content = data["choices"][0]["message"]["content"]

                # --- (Rest of the JSON parsing logic remains the same) ---
                 # Parse the response as JSON
                try:
                    parsed_data = json.loads(raw_content)

                    # Validate the structure
                    if (isinstance(parsed_data, dict) and
                        "storySegment" in parsed_data and
                        "choices" in parsed_data and
                        isinstance(parsed_data["choices"], list) and
                        len(parsed_data["choices"]) >= 2):

                        logger.info("Successfully generated story segment with valid structure")
                        return parsed_data, raw_content
                    else:
                        logger.error(f"Response has invalid structure: {raw_content}")
                        return None, raw_content

                except json.JSONDecodeError:
                    logger.warning(f"Direct JSON parsing failed for response: {raw_content}")
                    # If direct parsing fails, try to find JSON in the text
                    try:
                        # Look for JSON code block
                        json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
                        # import re # Re-import not needed if already imported at top
                        json_match = re.search(json_pattern, raw_content)
                        if json_match:
                            inner_json = json_match.group(1).strip()
                            parsed_data = json.loads(inner_json)
                            # Re-validate structure after extraction
                            if (isinstance(parsed_data, dict) and
                                "storySegment" in parsed_data and
                                "choices" in parsed_data and
                                isinstance(parsed_data["choices"], list) and
                                len(parsed_data["choices"]) >= 2):
                                logger.info("Successfully extracted JSON from code block")
                                return parsed_data, raw_content
                            else:
                                logger.error(f"Extracted JSON from code block has invalid structure: {inner_json}")
                                return None, raw_content
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON from code block: {e}")
                        pass # Continue to next fallback

                    # Try one more approach - find the first '{' and last '}'
                    try:
                        json_start = raw_content.find('{')
                        json_end = raw_content.rfind('}') + 1

                        if json_start >= 0 and json_end > json_start:
                            json_content = raw_content[json_start:json_end]
                            parsed_data = json.loads(json_content)
                             # Re-validate structure after extraction
                            if (isinstance(parsed_data, dict) and
                                "storySegment" in parsed_data and
                                "choices" in parsed_data and
                                isinstance(parsed_data["choices"], list) and
                                len(parsed_data["choices"]) >= 2):
                                logger.info("Successfully extracted JSON from text boundaries")
                                return parsed_data, raw_content
                            else:
                                logger.error(f"Extracted JSON from text boundaries has invalid structure: {json_content}")
                                return None, raw_content
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON from text boundaries: {e}")
                        pass # Final fallback

                    logger.error(f"Failed to parse response as JSON after multiple attempts: {raw_content}")
                    return None, raw_content

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during story generation: {e.response.status_code} {e.response.text}")
            return None, f"API Error: {e.response.status_code}, {e.response.text}"
        except Exception as e:
            logger.error(f"Unexpected error during story generation: {str(e)}", exc_info=True) # Add exc_info for traceback
            return None, f"Error: {str(e)}"

    def should_trigger_summary(self, turn_number: int) -> bool:
        """Check if this turn should trigger a summary update"""
        # Ensure turn_number is treated correctly (e.g., starts from 1)
        # If turn_number starts from 0, use (turn_number + 1) % interval == 0
        return turn_number > 0 and turn_number % SUMMARIZE_TURN_INTERVAL == 0

    def format_user_action(self, action: Dict[str, Any]) -> str:
        """Format a user action into a text representation"""
        if "choice" in action and action["choice"]:
            return f"My choice: {action['choice']}"
        elif "customInput" in action and action["customInput"]:
            return f"My custom action: {action['customInput']}"
        else:
            # Log the unexpected action structure
            logger.warning(f"Formatting an action with unexpected structure: {action}")
            return "No valid action provided." # Or perhaps raise an error?

    def find_prompt_for_turn(self, prompts: List[Dict[str, Any]], turn_number: int) -> Optional[str]:
        """Find the appropriate system prompt for the current turn"""
        valid_prompts = [p for p in prompts if
                         p.get("turn_start") is not None and p.get("system_prompt") and # Basic validation
                         p["turn_start"] <= turn_number and
                         (p.get("turn_end") is None or p["turn_end"] >= turn_number)]

        if not valid_prompts:
            logger.warning(f"No valid system prompt found for turn number {turn_number}")
            return None # Explicitly return None if none found

        # Sort by turn_start descending to prioritize more specific prompts if overlapping
        # (Assuming higher turn_start means more specific for overlapping ranges)
        # Can add explicit priority field later if needed.
        valid_prompts.sort(key=lambda p: p["turn_start"], reverse=True)

        logger.debug(f"Found {len(valid_prompts)} valid prompts for turn {turn_number}. Using prompt starting at turn {valid_prompts[0]['turn_start']}.")
        return valid_prompts[0]["system_prompt"]

# --- END OF FILE story_service.py ---