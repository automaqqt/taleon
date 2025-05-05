# --- START OF FILE services/summary_service.py ---

import os
import json
import logging
from dotenv import load_dotenv
import httpx
import re
import copy # Import copy for deepcopy
from typing import List, Dict, Any, Optional, Tuple

# Assuming you have this utility for robust JSON parsing
from ..utils.json_clean import robust_json_load

# Setup logging
logging.basicConfig(level=logging.DEBUG, # Use DEBUG to see merge details
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# Default values
DEFAULT_SUMMARY_MODEL = os.getenv("DEFAULT_SUMMARY_MODEL", "google/gemini-2.5-flash-preview")
DEFAULT_ANALYSIS_MODEL = os.getenv("DEFAULT_ANALYSIS_MODEL", "google/gemini-2.5-flash-preview")
DEFAULT_TEMPERATURE_SUMMARY = 0.45
DEFAULT_TEMPERATURE_ANALYSIS = 0.2

# API URLs and Keys
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Values returned by analysis prompt that indicate no change or no value found
# Make this case-insensitive comparison? For now, exact match.
IGNORE_SCALAR_VALUES = {None, "unchanged", "Unknown", "N/A", "unknown", "[Not Applicable]", ""}


class SummaryService:
    def __init__(self, api_key=None, api_url=None, default_summary_model=None, default_analysis_model=None):
        """Initialize the summary service"""
        self.openrouter_api_key = api_key or OPENROUTER_API_KEY
        self.openrouter_api_url = api_url or OPENROUTER_API_URL
        self.default_summary_model = default_summary_model or DEFAULT_SUMMARY_MODEL
        self.default_analysis_model = default_analysis_model or DEFAULT_ANALYSIS_MODEL

        if not self.openrouter_api_key:
            logger.warning("No OpenRouter API key provided. Summary/Analysis API calls may fail.")

    # --- analyze_story_elements (Corrected f-string) ---
    async def analyze_story_elements(
        self,
        system_prompt: str,
        recent_texts: List[str],
        existing_elements: Dict[str, Any],
        model: str = None,
        temperature: float = DEFAULT_TEMPERATURE_ANALYSIS
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Analyze a story segment using the provided system prompt.
        """
        model_to_use = model or self.default_analysis_model
        story_text_to_analyze = "\n".join(recent_texts)

        # Prepare the user message (CORRECTED f-string)
        existing_elements_json = json.dumps(existing_elements, indent=2, ensure_ascii=False)
        user_message = f"""Existing elements to compare against:
{existing_elements_json}

Story text to analyze:
--- START TEXT ---
{story_text_to_analyze}
--- END TEXT ---

Provide ONLY the JSON output containing NEW or CHANGED elements as defined in the system prompt."""

        try:
            headers = { "Content-Type": "application/json", "Authorization": f"Bearer {self.openrouter_api_key}" }
            payload = {
                "model": model_to_use,
                "messages": [ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_message} ],
                "temperature": temperature, "response_format": {"type": "json_object"}, "max_tokens": 1500
            }
            logger.info(f"Sending story analysis request using model: {model_to_use}")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                if not data.get("choices"): logger.error(f"No 'choices' in analysis API response from {model_to_use}. Response: {data}"); return None, str(data)
                message_content = data["choices"][0].get("message", {}).get("content")
                if not message_content: logger.error(f"Empty 'content' in analysis API response choice from {model_to_use}. Response: {data}"); return None, str(data)
                raw_response_text = message_content
                parsed_data = robust_json_load(raw_response_text)
                if parsed_data: logger.info("Successfully parsed story analysis elements."); return parsed_data, raw_response_text
                else: logger.error(f"Failed to robustly parse JSON from analysis response: {raw_response_text}"); return None, raw_response_text
        except httpx.HTTPStatusError as e: error_body = e.response.text; logger.error(f"HTTP error during story analysis: {e.response.status_code} - {error_body[:500]}"); return None, f"API Error: {e.response.status_code}, {error_body}"
        except httpx.RequestError as e: logger.error(f"Request error during story analysis: {e}"); return None, f"Network/Request Error: {e}"
        except Exception as e: logger.exception(f"Unexpected error during story analysis: {str(e)}"); return None, f"Unexpected Server Error: {str(e)}"


    # --- generate_story_summary (Corrected f-string) ---
    async def generate_story_summary(
        self,
        system_prompt: str,
        existing_summary: str,
        recent_developments: List[str],
        model: str = None,
        temperature: float = DEFAULT_TEMPERATURE_SUMMARY
    ) -> Tuple[str, Optional[str]]:
        """
        Generate a condensed summary using the provided system prompt.
        """
        model_to_use = model or self.default_summary_model
        developments_text = "\n".join(recent_developments)

        # Prepare user prompt (CORRECTED f-string)
        user_prompt = f"""Existing Summary:
{existing_summary or "[No previous summary]"}

Recent Developments to incorporate:
{developments_text}

Provide ONLY the updated summary text as requested in the system prompt."""

        try:
            headers = { "Content-Type": "application/json", "Authorization": f"Bearer {self.openrouter_api_key}" }
            payload = {
                "model": model_to_use,
                "messages": [ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt} ],
                "temperature": temperature, "max_tokens": 1000
            }
            logger.info(f"Generating story summary using model: {model_to_use}")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                if not data.get("choices"): logger.error(f"No 'choices' in summary API response from {model_to_use}. Response: {data}"); return existing_summary, str(data)
                message_content = data["choices"][0].get("message", {}).get("content")
                if not message_content: logger.error(f"Empty 'content' in summary API response choice from {model_to_use}. Response: {data}"); return existing_summary, str(data)
                raw_response_text = message_content; new_summary_text = raw_response_text.strip()
                if len(new_summary_text) < 10: logger.warning(f"Generated summary seems too short ({len(new_summary_text)} chars). Returning existing summary. Raw: {raw_response_text}"); return existing_summary, raw_response_text
                logger.info(f"Successfully generated story summary ({len(new_summary_text)} chars)."); return new_summary_text, raw_response_text
        except httpx.HTTPStatusError as e: error_body = e.response.text; logger.error(f"HTTP error during summary generation: {e.response.status_code} - {error_body[:500]}"); return existing_summary, f"API Error: {e.response.status_code}, {error_body}"
        except httpx.RequestError as e: logger.error(f"Request error during summary generation: {e}"); return existing_summary, f"Network/Request Error: {e}"
        except Exception as e: logger.exception(f"Unexpected error during summary generation: {str(e)}"); return existing_summary, f"Unexpected Server Error: {str(e)}"


    # --- _merge_dicts_recursive (No changes needed) ---
    def _merge_dicts_recursive(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Recursively merges source dict into target dict."""
        for key, value in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._merge_dicts_recursive(target[key], value)
                elif value is not None:
                     if target[key] != value: target[key] = value
            else:
                if value is not None: target[key] = value

    # --- _merge_lists (No changes needed) ---
    def _merge_lists(self, target_list: List[Any], source_list: List[Any]) -> bool:
        """
        Merges source_list into target_list.
        Tries to merge based on 'name' or 'id' if it's a list of dicts.
        Otherwise, appends unique items. Returns True if target_list was modified.
        """
        if not source_list: return False
        modified = False
        identifier_key = None
        if (target_list and isinstance(target_list[0], dict) and
            source_list and isinstance(source_list[0], dict)):
            if 'name' in target_list[0] and 'name' in source_list[0]: identifier_key = 'name'
            elif 'id' in target_list[0] and 'id' in source_list[0]: identifier_key = 'id'

        if identifier_key:
            target_map = {item.get(identifier_key): item for item in target_list if isinstance(item, dict)}
            for source_item in source_list:
                if not isinstance(source_item, dict) or identifier_key not in source_item:
                     if source_item not in target_list: target_list.append(source_item); modified = True
                     continue
                item_id = source_item[identifier_key]
                if item_id in target_map:
                    existing_item = target_map[item_id]
                    if isinstance(existing_item, dict):
                         original_item_copy = copy.deepcopy(existing_item)
                         self._merge_dicts_recursive(existing_item, source_item)
                         if existing_item != original_item_copy: modified = True
                else:
                    target_list.append(source_item); modified = True
            return modified
        else:
            for item in source_list:
                 if item not in target_list: target_list.append(item); modified = True
            return modified


    # --- update_story_data_from_analysis (No changes needed from previous version) ---
    def update_story_data_from_analysis(
        self,
        existing_context: Dict[str, Any],
        analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merges new analysis results into the existing story context dictionary
        using a generic, type-driven approach.
        """
        if not isinstance(existing_context, dict):
             logger.error(f"MERGE ERROR: Existing context is not a dict ({type(existing_context)}). Returning original.")
             return copy.deepcopy(existing_context) if existing_context is not None else {}
        if not isinstance(analysis_results, dict):
             logger.warning(f"MERGE INFO: Analysis results is not a dict ({type(analysis_results)}). Returning original context.")
             return copy.deepcopy(existing_context)

        updated_context = copy.deepcopy(existing_context)
        logger.debug(f"Starting generic merge. Existing keys: {list(updated_context.keys())}. Analysis keys: {list(analysis_results.keys())}")

        for key, new_value in analysis_results.items():
            logger.debug(f"Processing analysis key: '{key}' (Type: {type(new_value)})")
            if key not in updated_context:
                if type(new_value) is not list:
                    if new_value not in IGNORE_SCALAR_VALUES:
                        updated_context[key] = new_value
                        logger.debug(f"  Added new key '{key}' with value type {type(new_value)}.")
                    else:
                        logger.debug(f"  Skipped adding new key '{key}' due to ignorable value: {new_value!r}")
                else:
                    updated_context[key] = new_value
                    logger.debug(f"  Added new key '{key}' with value type {type(new_value)}.")
            else:
                existing_value = updated_context[key]
                logger.debug(f"  Key '{key}' exists. Existing type: {type(existing_value)}, New type: {type(new_value)}")
                if isinstance(existing_value, dict) and isinstance(new_value, dict):
                    logger.debug(f"  Merging dictionaries for key '{key}'.")
                    self._merge_dicts_recursive(existing_value, new_value)
                elif isinstance(existing_value, list) and isinstance(new_value, list):
                    logger.debug(f"  Merging lists for key '{key}'.")
                    list_modified = self._merge_lists(existing_value, new_value)
                    if list_modified: logger.debug(f"  List for key '{key}' was modified.")
                    else: logger.debug(f"  List for key '{key}' was not modified.")
                else:
                    if new_value not in IGNORE_SCALAR_VALUES:
                        if existing_value != new_value:
                             updated_context[key] = new_value
                             logger.debug(f"  Replaced value for key '{key}' (Old type: {type(existing_value)}, New type: {type(new_value)}).")
                        else:
                            logger.debug(f"  Value for key '{key}' is the same. No change.")
                    else:
                         logger.debug(f"  Skipped replacing key '{key}' due to ignorable new value: {new_value!r}")

        logger.info(f"Generic merge complete. Final context keys: {list(updated_context.keys())}")
        return updated_context


    # --- prepare_elements_for_analysis (No changes needed) ---
    def prepare_elements_for_analysis(self, story_context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepares the existing story context for the analysis prompt."""
        potential_relevant_keys = [
            "side_character", "initial_task", "magic_elements", "obstacle",
            "reward", "main_character_trait", "main_character_wish",
            "cliffhanger_situation", "main_character", "setting", "language"
        ]
        elements_for_prompt = {}
        if not isinstance(story_context, dict): story_context = {}
        for key in potential_relevant_keys:
            internal_key = key
            if key == "side_character" and key not in story_context and "side_characters" in story_context:
                 internal_key = "side_characters"
            value = story_context.get(internal_key)
            if value is None:
                 if key in ["side_character", "magic_elements"]: value = []
                 else: value = ""
            elements_for_prompt[key] = value
        logger.debug(f"Prepared existing elements for analysis prompt: {list(elements_for_prompt.keys())}")
        return elements_for_prompt


    # --- _analyze_initial_context (No changes needed) ---
    async def _analyze_initial_context(self, context_text: str, initial_prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Helper function to call LLM for initial context analysis using a specific prompt."""
        if not self.openrouter_api_key: logger.warning("No OpenRouter API key found. Skipping initial context analysis."); return None
        if not context_text: logger.warning("Empty context text provided for initial analysis."); return None
        if not initial_prompt: logger.error("Initial extraction prompt is required for _analyze_initial_context."); return None
        try:
            headers = { "Content-Type": "application/json", "Authorization": f"Bearer {self.openrouter_api_key}" }
            payload = {
                "model": self.default_analysis_model, "messages": [ {"role": "system", "content": initial_prompt}, {"role": "user", "content": context_text} ],
                "temperature": DEFAULT_TEMPERATURE_ANALYSIS, "response_format": {"type": "json_object"}, "max_tokens": 1500
            }
            logger.info(f"Sending initial context for analysis using model: {self.default_analysis_model}")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                if not data.get("choices"): logger.error(f"No choices in LLM initial analysis response.{data}"); return None
                raw_content = data["choices"][0].get("message", {}).get("content", "")
                if not raw_content: logger.error("Empty content in LLM initial analysis response."); return None
                parsed_data = robust_json_load(raw_content)
                if parsed_data: logger.info("Successfully parsed initial story elements from LLM response."); return parsed_data
                else: logger.error(f"Failed to robustly parse JSON from initial analysis response: {raw_content}"); return None
        except httpx.HTTPStatusError as e: error_body = e.response.text; logger.error(f"HTTP error during initial context analysis: {e.response.status_code} - {error_body[:500]}"); return None
        except httpx.RequestError as e: logger.error(f"Request error during initial context analysis: {e}"); return None
        except Exception as e: logger.exception(f"Unexpected error during initial context analysis: {str(e)}"); return None

# --- END OF FILE services/summary_service.py ---