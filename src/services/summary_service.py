import os
import json
import logging
import httpx
from typing import List, Dict, Any, Optional, Tuple

from ..utils.json_clean import robust_json_load

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default values
DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"
ANALYSIS_MODEL = os.getenv("INITIAL_ANALYSIS_MODEL", "google/gemini-2.0-flash-exp:free")#google/gemini-2.5-pro-exp-03-25:free")
DEFAULT_TEMPERATURE = 0.25

# API URLs - can be configured via environment variables
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Analysis prompt template for extracting story elements
FAIRY_TALE_ANALYSIS_PROMPT = """# Multilingual Fairy Tale Analysis System - Differential Analysis

## CORE FUNCTION
You are a precise multilingual fairy tale analyst. Your task is to:
1. Analyze a generated fairy tale text
2. Compare it with existing characters and elements provided by the user
3. Extract ONLY NEW or CHANGED elements into a structured JSON format
4. Provide the output in the SAME language as the input

## LANGUAGE DETECTION
1. First, identify the language of the input text
2. Process the text and provide output in the SAME language as the input
3. Use appropriate language-specific terminology for fairy tale elements

## OUTPUT FORMAT
Return ONLY the following JSON structure without any introduction, commentary, or additional text:

{
  "side_character": [
    {
      "name": "string (name of the side character)",
      "trait": "string (character trait)",
      "wish": "string (inner wish or motivation)"
    }
  ],
  "initial_task": "string (original task or external mission of the main character)",
  "magic_elements": [
    "string (first magical aid or event)",
    "string (second magical aid or event)"
  ],
  "obstacle": "string (description of a specific obstacle that appears independently of the task)",
  "reward": "string (a possible reward/achievement)",
  "main_character_trait": "string (distinctive external characteristic or special trait of the main character)",
  "main_character_wish": "string (inner wish, goal or longing of the main character)",
  "cliffhanger_situation": "string (description of the tension-filled cliffhanger situation at the end of the current turn)",
  "language": "string (detected language of the input text)"
}

## COMPARISON RULES
1. Compare all elements with those provided in the user's input
2. Include ONLY new or modified elements in the output JSON
3. If an element already exists and remains unchanged, DO NOT include it in the output
4. If all elements in a category are unchanged, return an empty array or "unchanged" for that category

## EXTRACTION RULES
Follow these clear rules for each field:

1. **side_character**: 
   - Include ONLY characters who:
     - Actively participate in the fairy tale
     - Have their own wishes or motivations
     - Are NEW or CHANGED compared to the existing characters
   - For each side character, extract:
     - **name**: Character's name as provided in the text
     - **trait**: Dominant character trait
     - **wish**: Inner desire or motivation
   - Express all descriptions in the detected language

2. **initial_task**: 
   - Must be a clearly described action or mission (not a wish or emotion)
   - Include ONLY if it is NEW or DIFFERENT from the existing task
   - If unchanged, use "unchanged"

3. **magic_elements**: 
   - Include ONLY concrete magical items or beings that:
     - Have already been introduced in the story
     - Are NEW or CHANGED compared to existing magic elements
   - If all unchanged, return an empty array

4. **obstacle**: 
   - Description of a specific obstacle that appears independently of the task
   - Examples: river, thorn hedge, dark forest, mountain, storm
   - Must be a concrete physical or magical barrier
   - Include ONLY if it is NEW or DIFFERENT from existing obstacles
   - If unchanged, use "unchanged"

5. **reward**: 
   - A possible reward or achievement for the main character
   - Examples: magic ring, friendship with animal beings, special powers, treasure
   - Should be something concrete that the character can obtain or experience
   - Include ONLY if it is NEW or DIFFERENT from existing rewards
   - If unchanged, use "unchanged"

6. **main_character_trait**: 
   - Distinctive external characteristic or special trait of the main character
   - Examples: "red cap", "brave look", "golden hair", "unusual strength"
   - Focus on visible or notable characteristics
   - Include ONLY if it is NEW or DIFFERENT from existing traits
   - If unchanged, use "unchanged"

7. **main_character_wish**: 
   - Inner wish, goal or longing of the main character
   - Examples: "to find the lost star", "to save friendship", "to return home"
   - Should reflect emotional desires, not just external tasks
   - Include ONLY if it is NEW or DIFFERENT from existing wishes
   - If unchanged, use "unchanged"

8. **cliffhanger_situation**: 
   - Describe the threat or decision-making situation briefly
   - Use child-friendly language
   - Include ONLY if it represents a NEW situation
   - If unchanged, use "unchanged"

9. **language**:
   - Indicate the detected language of the original text (e.g., "German", "English", "French")
"""

INITIAL_ELEMENT_EXTRACTION_PROMPT = """# Multilingual Fairy Tale Analysis System

## CORE FUNCTION
You are a precise multilingual fairy tale analyst. Your task is to extract specific information from fairy tale texts in any language and return it in a structured JSON format, following strict guidelines.

## LANGUAGE DETECTION
1. First, identify the language of the input text
2. Process the text and provide output in the SAME language as the input
3. Use appropriate language-specific terminology for fairy tale elements

## OUTPUT FORMAT
Return ONLY the following JSON structure without any introduction, commentary, or additional text:

{
  "original_tale_context": "string (concise but complete summary of the original fairy tale context, max 6 sentences with total 500 words)",
  "main_character": "string (name of the main character)",
  "main_character_trait": "string (most important character trait, max 10 words)",
  "main_character_wish": "string (inner wish or goal of the main character, max 15 words)",
  "side_character": [
    {
      "name": "string (name of the side character)",
      "trait": "string (character trait)",
      "wish": "string (inner wish or motivation)"
    }
  ],
  "setting": "string (location and general time description, max 40 words)",
  "language": "string (detected language of the input text)"
}

## EXTRACTION RULES
Follow these clear rules for each field:

1. **original_tale_context**: 
   - Identify the central starting point of the plot, world, and magical elements
   - Focus on key narrative elements, not minor details but keep the full story intact
   - Use child-friendly, fairy tale-appropriate language in the detected language

3. **main_character**: 
   - Identify only the central figure (not a side character)
   - Use the character's full name as provided in the text

4. **main_character_trait**: 
   - Extract the dominant character trait
   - Use concise description (not a lengthy explanation)
   - Express in the detected language

5. **main_character_wish**: 
   - Identify the inner desire or emotional goal (not external objective)
   - Express in the detected language

6. **side_character**: 
   - Include ALL important side characters who repeatedly act or help
   - For each side character, extract:
     - **name**: Character's name as provided in the text
     - **trait**: Dominant character trait
     - **wish**: Inner desire or motivation
   - Express all descriptions in the detected language

7. **setting**: 
   - Describe both location and time period
   - Use fairy tale language appropriate to the detected culture
   - Express in the detected language

8. **language**:
   - Indicate the detected language of the original text (e.g., "German", "English", "French")

## LANGUAGE-SPECIFIC GUIDELINES

### ENGLISH
- Use traditional fairy tale terminology: "enchanted", "magical", "spell", etc.
- Focus on moral lessons and character growth typical in English fairy tales

### GERMAN (DEUTSCH)
- Use traditional German fairy tale terminology: "verzaubert", "magisch", "Zauberspruch", etc.
- Pay attention to "Waldeinsamkeit" (forest solitude) and natural elements common in German tales

### FRENCH (FRANÇAIS)
- Use traditional French fairy tale terminology: "enchanté", "magique", "sortilège", etc.
- Note the importance of social status and transformation common in French tales

### SPANISH (ESPAÑOL)
- Use traditional Spanish fairy tale terminology: "encantado", "mágico", "hechizo", etc.
- Recognize themes of family honor and divine intervention common in Spanish tales

### OTHER LANGUAGES
- Adapt terminology to match the cultural context of the detected language
- Preserve cultural elements specific to the tale's origin

## QUALITY CONTROL
Before submitting your response, verify:

1. Is the JSON correctly structured with all required fields?
2. Have you used only information explicitly stated or strongly implied in the text?
3. Have you avoided inventing new characters, wishes, or locations?
4. Is your language child-friendly and appropriate to the detected language?
5. Have you used "unknown" (or its equivalent in the detected language) for any unavailable information?
6. Are all descriptions within the specified word limits?

## IMPORTANT NOTES
- If certain elements are not mentioned in the text, use "unknown" or its equivalent in the detected language
- Never invent information not present in the text
- Use child-friendly, fairy tale language appropriate to the culture
- DO NOT add any explanations, introductions, or additional text outside the JSON
- The text to analyze will be provided by the user

## MULTILINGUAL EXAMPLES

### Example Input (German):
"Es war einmal ein kleines Mädchen namens Rotkäppchen, das in einem Dorf am Rande des Waldes lebte. Sie war bekannt für ihre Freundlichkeit zu Tieren und ihren roten Umhang. Rotkäppchens Großmutter war krank, und Rotkäppchen wünschte sich, ihr Trost zu bringen. Der böse Wolf, listig und hungrig, wollte sowohl Rotkäppchen als auch ihre Großmutter fressen. Der Jäger, stark und wachsam, patrouillierte im Wald, um alle zu beschützen."

### Example Output (German):
{
  "original_tale_context": "Eine Version von Rotkäppchen, in der ein junges Mädchen ihre kranke Großmutter besucht, während sie von einem Wolf im verzauberten Wald verfolgt wird und dabei auf Gegner aus unbekannten Welten trifft. Diese helfen",
  "tale_id": "P-001",
  "main_character": "Rotkäppchen",
  "main_character_trait": "freundlich zu Tieren",
  "main_character_wish": "ihrer Großmutter Trost zu bringen",
  "side_character": [
    {
      "name": "Wolf",
      "trait": "böse und listig",
      "wish": "Rotkäppchen und ihre Großmutter zu fressen"
    },
    {
      "name": "Jäger",
      "trait": "stark und wachsam",
      "wish": "die Waldbewohner zu beschützen"
    },
    {
      "name": "Großmutter",
      "trait": "krank",
      "wish": "unbekannt"
    }
  ],
  "setting": "Ein Dorf am Rande des Waldes",
  "language": "Deutsch"
}

### Example Input (French):
"Il était une fois une petite fille nommée Petit Chaperon Rouge qui vivait dans un village à la lisière de la forêt. Elle était connue pour sa gentillesse envers les animaux et son chaperon rouge. La grand-mère du Petit Chaperon Rouge était malade, et le Petit Chaperon Rouge souhaitait lui apporter du réconfort. Le méchant loup, rusé et affamé, voulait manger à la fois le Petit Chaperon Rouge et sa grand-mère. Le bûcheron, fort et vigilant, patrouillait dans la forêt pour assurer la sécurité de tous."

### Example Output (French):
{
  "original_tale_context": "Une version du Petit Chaperon Rouge où une jeune fille rend visite à sa grand-mère malade tout en étant suivie par un loup dans une forêt enchantée",
  "tale_id": "P-001",
  "main_character": "Petit Chaperon Rouge",
  "main_character_trait": "gentille envers les animaux",
  "main_character_wish": "apporter du réconfort à sa grand-mère",
  "side_character": [
    {
      "name": "Loup",
      "trait": "méchant et rusé",
      "wish": "manger le Petit Chaperon Rouge et sa grand-mère"
    },
    {
      "name": "Bûcheron",
      "trait": "fort et vigilant",
      "wish": "assurer la sécurité des habitants de la forêt"
    },
    {
      "name": "Grand-mère",
      "trait": "malade",
      "wish": "inconnu"
    }
  ],
  "setting": "Un village à la lisière de la forêt",
  "language": "Français"
}

## FINAL REMINDER
Your ONLY response should be the correctly formatted JSON in the SAME language as the input. No additional text.
"""


class SummaryService:
    def __init__(self, api_key=None, api_url=None, model=None):
        """Initialize the summary service with optional custom API settings"""
        self.openrouter_api_key = api_key or OPENROUTER_API_KEY
        self.openrouter_api_url = api_url or OPENROUTER_API_URL
        self.default_model = model or DEFAULT_MODEL
        
        if not self.openrouter_api_key:
            logger.warning("No OpenRouter API key provided. API calls will fail.")
    
    async def analyze_story_elements(
        self, 
        recent_texts: List[str], 
        existing_elements: Dict[str, Any],
        model: str = None,
        temperature: float = DEFAULT_TEMPERATURE
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Analyze a story segment and identify new or changed elements
        
        Args:
            recent_texts: List of recent story segments/messages to analyze
            existing_elements: Dictionary of existing story elements to compare against
            model: Optional model override
            temperature: Temperature setting for the LLM (0-1)
            
        Returns:
            Tuple containing (parsed summary data, raw LLM response)
        """
        model_to_use = model or self.default_model
        
        # Prepare the user message with existing elements and text to analyze
        story_text = "\n".join(recent_texts)
        
        user_message = f"""Existing elements:
{json.dumps(existing_elements, indent=2, ensure_ascii=False)}

Story part to analyze:
{story_text}"""

        # Call the LLM API
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openrouter_api_key}"
            }
            
            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": FAIRY_TALE_ANALYSIS_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "max_tokens": 2000
            }
            
            logger.info(f"Sending story analysis request using model: {model_to_use}")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                if "choices" not in data or not data["choices"]:
                    logger.error("No choices in API response")
                    return None, str(data)
                
                raw_content = data["choices"][0]["message"]["content"]
                
                # Extract JSON content
                try:
                    # Try to parse as valid JSON directly first
                    parsed_data = json.loads(raw_content)
                    logger.info("Successfully extracted story elements")
                    return parsed_data, raw_content
                except json.JSONDecodeError:
                    # If that fails, try to find JSON within the text
                    logger.warning("JSON parsing failed, attempting to extract JSON from text")
                    json_start = raw_content.find('{')
                    json_end = raw_content.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        # Found potential JSON content
                        json_content = raw_content[json_start:json_end]
                        try:
                            parsed_data = json.loads(json_content)
                            parsed_data = robust_json_load(raw_content)
                            logger.info("Successfully extracted JSON from text")
                            return parsed_data, raw_content
                        except json.JSONDecodeError:
                            logger.error("Failed to parse extracted JSON content")
                    
                    logger.error("Could not find valid JSON in response")
                    return None, raw_content
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during story analysis: {e.response.status_code} {e.response.text}")
            return None, f"API Error: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Error during story analysis: {str(e)}")
            return None, f"Error: {str(e)}"
    
    async def generate_story_summary(
        self, 
        existing_summary: str,
        recent_developments: List[str],
        tale_title: str,
        model: str = None,
        custom_prompt: str = None,
        temperature: float = 0.7
    ) -> Tuple[str, Optional[str]]:
        """
        Generate a condensed summary of story progress
        
        Args:
            existing_summary: Current summary of the story
            recent_developments: Recent story segments to summarize
            tale_title: Title of the tale
            model: Optional model override
            custom_prompt: Optional custom system prompt
            temperature: Temperature setting for the LLM (0-1)
            
        Returns:
            Tuple containing (new summary text, raw LLM response)
        """
        model_to_use = model or self.default_model
        
        # Default system prompt if none provided
        system_prompt = custom_prompt or f"""You are an expert story summarizer. Condense the 'Existing Summary' and 'Recent Developments' into a single, updated, concise summary capturing the current plot state, characters, and setting of this interactive story based on the tale '{tale_title}'. Focus on information needed to continue the story logically. Output ONLY the updated summary text. DO IT IN GERMAN"""
        
        # Format the user prompt with existing summary and recent developments
        developments_text = "\n".join(recent_developments)
        user_prompt = f"""Existing Summary:
{existing_summary}

Recent Developments:
{developments_text}

Updated Summary:"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openrouter_api_key}"
            }
            
            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": 1000
            }
            
            logger.info(f"Generating story summary using model: {model_to_use}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.openrouter_api_url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                if "choices" not in data or not data["choices"]:
                    logger.error("No choices in API response")
                    return existing_summary, str(data)
                
                raw_content = data["choices"][0]["message"]["content"]
                summary_text = raw_content.strip()
                
                # Validate the summary quality
                if not summary_text or len(summary_text) < 50:
                    logger.warning("Generated summary is too short, using existing summary")
                    return existing_summary, raw_content
                
                logger.info(f"Successfully generated story summary ({len(summary_text)} chars)")
                return summary_text, raw_content
                
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return existing_summary, f"Error: {str(e)}"

    def update_story_data_from_analysis(self, story_data: Dict[str, Any], analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update story data with new analysis results, applying differential changes
        
        Args:
            story_data: Existing story data dictionary
            analysis_results: New analysis results to integrate
            
        Returns:
            Updated story data dictionary
        """
        # Create a copy of the story data to avoid modifying the original
        updated_data = story_data.copy()
        
        # Process side characters - we need to merge rather than replace
        if "side_character" in analysis_results and isinstance(analysis_results["side_character"], list):
            if not updated_data.get("side_characters"):
                updated_data["side_characters"] = []
                
            for new_character in analysis_results["side_character"]:
                # Check if this character already exists
                char_exists = False
                for i, existing_char in enumerate(updated_data["side_characters"]):
                    if existing_char.get("name") == new_character.get("name"):
                        # Update existing character with new info
                        updated_data["side_characters"][i] = new_character
                        char_exists = True
                        break
                
                # If it's a new character, add it
                if not char_exists:
                    updated_data["side_characters"].append(new_character)
        
        # Process magic elements - similar to side characters
        if "magic_elements" in analysis_results and isinstance(analysis_results["magic_elements"], list):
            if not updated_data.get("magic_elements"):
                updated_data["magic_elements"] = []
                
            # Add only new magic elements
            for element in analysis_results["magic_elements"]:
                if element not in updated_data["magic_elements"]:
                    updated_data["magic_elements"].append(element)
        
        # Process scalar fields - only update if the value is new and not "unchanged"
        scalar_fields = [
            ("initial_task", "initial_task"),
            ("obstacle", "obstacle"),
            ("reward", "reward"),
            ("main_character_trait", "main_character_trait"),
            ("main_character_wish", "main_character_wish"),
            ("cliffhanger_situation", "cliffhanger_situation")
        ]
        
        for src_field, dest_field in scalar_fields:
            if src_field in analysis_results and analysis_results[src_field] != "unchanged":
                updated_data[dest_field] = analysis_results[src_field]
                
        # Add language if it's not already set
        if "language" in analysis_results and not updated_data.get("language"):
            updated_data["language"] = analysis_results["language"]
                
        return updated_data

    def prepare_elements_for_analysis(self, story_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare existing story elements in the format expected by the analysis function
        
        Args:
            story_data: Dictionary containing story data
            
        Returns:
            Dictionary with elements formatted for analysis
        """
        elements = {
            "side_character": story_data.get("side_characters", []),
            "initial_task": story_data.get("initial_task", ""),
            "magic_elements": story_data.get("magic_elements", []),
            "obstacle": story_data.get("obstacle", ""),
            "reward": story_data.get("reward", ""),
            "main_character_trait": story_data.get("main_character_trait", ""),
            "main_character_wish": story_data.get("main_character_wish", ""),
            "cliffhanger_situation": story_data.get("cliffhanger_situation", "")
        }
        
        return elements
    
    async def _analyze_initial_context(self, context_text: str) -> Optional[Dict[str, Any]]:
        """Helper function to call LLM for initial context analysis."""
        if not OPENROUTER_API_KEY:
            logger.warning("No OpenRouter API key found. Skipping initial context analysis.")
            return None
        if not context_text:
            logger.warning("Empty context text provided. Skipping initial context analysis.")
            return None

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_API_KEY}"
            }
            payload = {
                "model": ANALYSIS_MODEL,
                "messages": [
                    {"role": "system", "content": INITIAL_ELEMENT_EXTRACTION_PROMPT},
                    {"role": "user", "content": context_text}
                ],
                "temperature": 0.2, # Low temp for deterministic extraction
                "response_format": {"type": "json_object"},
                "max_tokens": 1000 # Adjust as needed
            }
            logger.info(f"Sending initial context for analysis using model: {ANALYSIS_MODEL}")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                response.raise_for_status() # Raise exception for 4xx/5xx errors

                data = response.json()
                if not data.get("choices"):
                    logger.error("No choices in LLM analysis response.")
                    return None

                raw_content = data["choices"][0].get("message", {}).get("content", "")
                if not raw_content:
                    logger.error("Empty content in LLM analysis response.")
                    return None

                # Try parsing JSON
                try:
                    parsed_data = json.loads(raw_content)
                    logger.info(f"Successfully parsed initial story elements from LLM response.{parsed_data}")
                    return parsed_data
                except json.JSONDecodeError:
                    # Attempt to extract JSON from text if direct parsing fails
                    logger.warning("Direct JSON parsing failed for analysis response. Attempting extraction.")
                    try:
                        # json_start = raw_content.find('{')
                        # json_end = raw_content.rfind('}') + 1
                        # if json_start >= 0 and json_end > json_start:
                        #     json_content = raw_content[json_start:json_end]
                        #     parsed_data = json.loads(json_content)
                        #     logger.info("Successfully extracted initial story elements from text.")
                        print(raw_content)
                        parsed_data = robust_json_load(raw_content)
                        return parsed_data
                        # else:
                        #     logger.error(f"Could not find valid JSON markers in analysis response: {raw_content}")
                        #     return None
                    except Exception as e_extract:
                        logger.error(f"Error extracting/parsing JSON from analysis response: {e_extract}. Raw: {raw_content}")
                        return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during initial context analysis: {e.response.status_code} - {e.response.text}")
            return None # Don't block base story creation, just skip elements
        except Exception as e:
            logger.error(f"Unexpected error during initial context analysis: {str(e)}", exc_info=True)
            return None # Don't block base story creation