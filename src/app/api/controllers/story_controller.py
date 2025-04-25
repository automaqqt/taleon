from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

from ....database.db_utils import (
    get_db, get_all_base_stories, get_base_story, create_user_story, 
    get_user_story, get_user_stories, update_user_story, add_story_message,
    get_story_prompts_for_turn, update_story_summary_data
)
from ....services.story_service import StoryService, VALID_STORY_CONFIG_KEYS, DEFAULT_TEMPERATURE
from ....services.summary_service import SummaryService
logger = logging.getLogger(__name__)

# Set up the services
story_service = StoryService()
summary_service = SummaryService()


# Define Pydantic models for request/response
class StoryAction(BaseModel):
    """User action that can be either a choice or a custom input"""
    choice: Optional[str] = None
    customInput: Optional[str] = None

class DebugConfig(BaseModel):
    """Configuration for debugging and prompt engineering"""
    storyModel: Optional[str] = None
    summaryModel: Optional[str] = None
    systemPrompt: Optional[str] = None
    summarySystemPrompt: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=1.0, description="Controls randomness")

class GenerateSegmentRequest(BaseModel):
    """Request structure for generating story segments"""
    storyId: str
    userId: str
    currentTurnNumber: int = 0
    action: StoryAction
    debugConfig: Optional[DebugConfig] = None

class ListStoriesRequest(BaseModel):
    """Request to list stories for a user"""
    userId: str
    includeCompleted: bool = False

class CreateStoryRequest(BaseModel):
    """Request to create a new story"""
    userId: str
    baseStoryId: str
    title: Optional[str] = None

class SummarizeStoryRequest(BaseModel):
    """Request to trigger a story summarization"""
    storyId: str
    
class StoryResponse(BaseModel):
    """Response structure for story operations"""
    storySegment: str
    choices: List[str]
    updatedSummary: str
    nextTurnNumber: int
    storyId: str
    rawResponse: Optional[str] = None
    errorMessage: Optional[str] = None

class StoryMetadata(BaseModel):
    """Basic metadata about a story"""
    id: str
    title: str
    currentTurnNumber: int
    baseStoryTitle: str
    isCompleted: bool
    updatedAt: str
    createdAt: str

class UserStoryDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    user_id: str
    base_story_id: str
    baseStoryTitle: Optional[str] = None # Added for frontend convenience
    currentSummary: Optional[str] = None
    currentTurnNumber: int
    isCompleted: bool
    storyMessages: List[Dict[str, Any]] = [] # Example type, adjust as needed
    last_choices: Optional[List[str]] = None # <-- ADD THIS FIELD
    createdAt: Optional[datetime] = None # Use alias or format later if needed
    updatedAt: Optional[datetime] = None

    class Config:
        orm_mode = True # Or from_attributes = True for Pydantic v2


# Create router
router = APIRouter()

@router.get("/base-stories", response_model=List[Dict[str, Any]])
async def get_available_base_stories():
    """Returns a list of available base stories that users can start from"""
    try:
        base_stories = get_all_base_stories()
        
        # Format response - include only needed fields
        formatted_stories = []
        for story in base_stories:
            formatted_stories.append({
                "id": story.id,
                "title": story.title,
                "description": story.description,
                "language": story.language,
                "is_active": story.is_active
            })
            
        return formatted_stories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve base stories: {str(e)}"
        )

@router.post("/stories", response_model=Dict[str, Any])
async def create_new_story(request: CreateStoryRequest):
    """Creates a new story based on a template"""
    try:
        # Get the base story
        base_story = get_base_story(request.baseStoryId)
        if not base_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Base story with ID {request.baseStoryId} not found"
            )
        
        # Create a new user story
        user_story = create_user_story(
            user_id=request.userId,
            base_story_id=request.baseStoryId,
            title=request.title or f"{base_story.title}'s Adventure"
        )
        
        return {
            "id": user_story.id,
            "title": user_story.title,
            "baseStoryTitle": base_story.title,
            "currentTurnNumber": user_story.current_turn_number,
            "currentSummary": user_story.current_summary,
            "isCompleted": user_story.is_completed,
            "createdAt": user_story.created_at.isoformat(),
            "updatedAt": user_story.updated_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create story: {str(e)}"
        )

@router.get("/stories", response_model=List[StoryMetadata])
async def list_user_stories(userId: str, includeCompleted: bool = False):
    """Returns a list of stories for a user"""
    try:
        user_stories = get_user_stories(userId, completed=None if includeCompleted else False)
        
        # Format the response
        stories_list = []
        for story in user_stories:
            base_story = get_base_story(story.base_story_id)
            base_title = base_story.title if base_story else "Unknown"
            
            stories_list.append({
                "id": story.id,
                "title": story.title,
                "currentTurnNumber": story.current_turn_number,
                "baseStoryTitle": base_title,
                "isCompleted": story.is_completed,
                "updatedAt": story.updated_at.isoformat(),
                "createdAt": story.created_at.isoformat()
            })
        
        return stories_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stories: {str(e)}"
        )

@router.post("/generate-segment", response_model=StoryResponse)
async def generate_story_segment(request: GenerateSegmentRequest, background_tasks: BackgroundTasks):
    """Generates the next story segment based on user action and context"""
    user_story = None # Initialize for broader scope in error handling
    base_story = None # Initialize for broader scope
    try:
        # --- Get UserStory and BaseStory ---
        print(request.storyId)
        user_story = get_user_story(request.storyId)
        if not user_story:
            logger.warning(f"Story not found for ID: {request.storyId}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Story with ID {request.storyId} not found"
            )

        base_story = get_base_story(user_story.base_story_id)
        if not base_story:
            # This case indicates potential data inconsistency
            logger.error(f"Base story ID {user_story.base_story_id} referenced by UserStory {request.storyId} not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, # Or 500 Internal Server Error might be appropriate
                detail=f"Base story associated with story ID {request.storyId} not found"
            )

        # --- Validate Turn Number ---
        # print(user_story.id)
        # if request.currentTurnNumber != user_story.current_turn_number:
        #     logger.warning(f"Turn number mismatch for story {request.storyId}. Expected {user_story.current_turn_number}, got {request.currentTurnNumber}")
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail=f"Turn number mismatch. Expected {user_story.current_turn_number}, got {request.currentTurnNumber}"
        #     )

        # --- 1. Format User Action and Add to History ---
        # Make sure request.action exists and is not None
        if request.action is None:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No action provided in the request."
            )
        formatted_action = story_service.format_user_action(request.action.dict(exclude_none=True))
        add_story_message(
            request.storyId,
            "userInput" if request.action.customInput else "choice",
            formatted_action,
            user_story.current_turn_number
        )

        # Reload user_story to get the updated history if get_user_story doesn't return a live object
        # or if add_story_message doesn't update the passed object in place.
        # If your ORM handles this automatically, you might not need to reload.
        user_story = get_user_story(request.storyId) # Re-fetch to include the new message
        story_history = user_story.story_messages or [] # Handle potential None
        

        # --- 2. Check for Summarization Trigger ---
        should_summarize = story_service.should_trigger_summary(user_story.current_turn_number)

        # --- 3. Get System Prompt ---
        valid_prompts = get_story_prompts_for_turn(base_story.id, user_story.current_turn_number)
        system_prompt = None

        if request.debugConfig and request.debugConfig.systemPrompt:
            system_prompt = request.debugConfig.systemPrompt
            logger.debug(f"Using debug system prompt for story {request.storyId}")
        elif valid_prompts:
            # Assuming get_story_prompts_for_turn returns sorted or has defined priority
            system_prompt = valid_prompts[0].system_prompt
            logger.debug(f"Using prompt defined for turn >= {valid_prompts[0].turn_start} for story {request.storyId}")
        elif base_story.initial_system_prompt:
             system_prompt = base_story.initial_system_prompt
             logger.debug(f"Falling back to base story initial prompt for story {request.storyId}")
        else:
            logger.error(f"No system prompt could be determined for story {request.storyId}, turn {user_story.current_turn_number}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cannot determine system prompt for story generation."
            )

        # --- 4. Prepare Story Configuration Data for Injection ---
        # Define the keys expected from the UserStory model based on VALID_STORY_CONFIG_KEYS
        # Exclude keys handled dynamically by the service or not stored on UserStory
        user_story_db_keys = [
            key for key in VALID_STORY_CONFIG_KEYS
            if key not in {"current_summary", "original_tale_context", "base_story_title"} # Exclude dynamic/base story keys
        ]

        story_config_data = {}
        for key in user_story_db_keys:
            if hasattr(user_story, key):
                story_config_data[key] = getattr(user_story, key)
            else:
                # Log if a defined key isn't an attribute, might indicate mismatch
                logger.warning(f"UserStory object (ID: {user_story.id}) missing expected config attribute '{key}'")
                story_config_data[key] = None # Set to None if missing

        # Add base story title if it's a valid key for injection (ensure it's in VALID_STORY_CONFIG_KEYS)
        if "base_story_title" in VALID_STORY_CONFIG_KEYS:
            if hasattr(base_story, "title"):
                 story_config_data["base_story_title"] = base_story.title
            else:
                 logger.warning(f"BaseStory object (ID: {base_story.id}) missing 'title' attribute for injection.")
                 story_config_data["base_story_title"] = "[Unknown Tale Title]"

        logger.debug(f"Story config data prepared for injection: {story_config_data}")

        # --- 5. Get LLM Configuration ---
        story_model = request.debugConfig.storyModel if request.debugConfig and request.debugConfig.storyModel else None
        summary_model = request.debugConfig.summaryModel if request.debugConfig and request.debugConfig.summaryModel else None
        temperature = request.debugConfig.temperature if request.debugConfig and request.debugConfig.temperature is not None else DEFAULT_TEMPERATURE # Use imported default

        # --- 6. Generate the Story Segment (Passing story_config_data) ---
        #print(story_history)
        story_history_text = [msg.get("content", "") for msg in story_history if isinstance(msg, dict)] # Safer extraction
        #print(story_history_text)
        llm_response, raw_response = await story_service.generate_story_segment(
            system_prompt=system_prompt, # Pass the base prompt with placeholders
            history=story_history_text,
            current_summary=user_story.current_summary or "", # Ensure not None
            original_tale_context=base_story.original_tale_context or "", # Ensure not None
            story_config=story_config_data, # Pass the extracted config data
            model=story_model, # Will use service default if None
            temperature=temperature
        )

        if not llm_response:
            logger.error(f"Failed to generate/parse story segment for story {request.storyId}. Raw response: {raw_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate story segment. LLM response issue. Raw: {raw_response or 'N/A'}"
            )

        # --- 7. Add Generated Segment to History ---
        add_story_message(
            request.storyId,
            "story",
            llm_response["storySegment"], # Assuming validation happened in service
            user_story.current_turn_number # The turn number *for* this new message
        )

        # --- 8. Update User Story State ---
        next_turn = user_story.current_turn_number + 1
        choices_to_save = llm_response.get("choices") # Get choices from LLM response

        # Use the existing update function from db_utils
        updated_story = update_user_story(
            request.storyId,
            current_turn_number=next_turn,
            last_choices=choices_to_save # <-- ADD THIS
        )

        if not updated_story:
             # Handle case where story couldn't be found for update (shouldn't happen if fetched earlier)
             logger.error(f"Failed to find story {request.storyId} during final update.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update story state.")


        # --- 9. Trigger Background Summarization if Needed ---
        if should_summarize:
            logger.info(f"Triggering background summarization for story {request.storyId} at turn {user_story.current_turn_number}")
            # Extract recent history again *after* adding the new segment, or pass history + new segment
            # Let's pass the history used *for* generation plus the new segment text
            history_for_summary = story_history_text + [llm_response["storySegment"]]
            background_tasks.add_task(
                summarize_story_background,
                story_id=request.storyId,
                current_summary=user_story.current_summary or "",
                recent_messages=history_for_summary[-10:], # Use last 10 interactions including new segment
                tale_title=base_story.title or "[Unknown Tale]",
                summary_model=summary_model, # Pass specific summary model if provided
                custom_prompt=(request.debugConfig.summarySystemPrompt
                                       if request.debugConfig and request.debugConfig.summarySystemPrompt
                                       else None),
                temperature=temperature # Can use same temp or have a separate setting
            )
            

        # --- 10. Prepare and Return Response ---
        response = StoryResponse(
            storySegment=llm_response["storySegment"],
            choices=choices_to_save or [],
            updatedSummary=user_story.current_summary or "", # Return current summary, bg task updates later
            nextTurnNumber=next_turn,
            storyId=request.storyId,
            rawResponse=raw_response, # Check debug flag
            errorMessage=None
        )
        logger.info(f"Successfully generated segment for story {request.storyId}, next turn {next_turn}")
        return response

    except HTTPException as he:
        # Log HTTPExceptions as warnings or errors depending on status code
        log_level = logging.ERROR if (he.status_code >= 500) else logging.WARNING
        logger.log(log_level, f"HTTPException in generate_story_segment for story {request.storyId}: {he.status_code} - {he.detail}")
        raise # Re-raise HTTPException to let FastAPI handle it

    except Exception as e:
        logger.exception(f"Unexpected error generating story segment for story {request.storyId}: {e}") # Use logger.exception to include traceback

        # Attempt to provide a graceful fallback response
        current_turn = user_story.current_turn_number if user_story else request.currentTurnNumber
        current_summary = user_story.current_summary if user_story else ""

        # Use Depends on status code? Maybe always return 500 here?
        # For now, let's stick with the original fallback structure but use status code
        # raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")

        # Or return the StoryResponse with error message:
        return StoryResponse(
             storySegment="Es tut mir leid, aber ein interner Fehler ist aufgetreten und ich konnte die Geschichte nicht fortsetzen. Bitte versuche es später erneut.",
             choices=[{"text": "Erneut versuchen (gleicher Spielzug)"}, {"text": "Zurück zur Übersicht"}], # Example choices for error state
             updatedSummary=current_summary,
             nextTurnNumber=current_turn, # Keep the current turn number so user can retry
             storyId=request.storyId,
             rawResponse=None,
             errorMessage=f"Ein unerwarteter Fehler ist aufgetreten: {str(e)}" # Provide error message
        )

@router.post("/summarize", response_model=Dict[str, Any])
async def summarize_story(request: SummarizeStoryRequest):
    """Trigger a summary update for a story"""
    try:
        # Get the user story
        user_story = get_user_story(request.storyId)
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Story with ID {request.storyId} not found"
            )
        
        # Get the base story
        base_story = get_base_story(user_story.base_story_id)
        if not base_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Base story with ID {user_story.base_story_id} not found"
            )
        
        # Get recent messages
        story_history = user_story.story_messages
        recent_messages = [msg["content"] for msg in story_history[-10:]]
        
        # Generate new summary
        new_summary, raw_response = await summary_service.generate_story_summary(
            user_story.current_summary,
            recent_messages,
            base_story.title
        )
        
        # Prepare existing elements for analysis
        existing_elements = summary_service.prepare_elements_for_analysis({
            "main_character_trait": user_story.main_character_trait,
            "main_character_wish": user_story.main_character_wish,
            "side_characters": user_story.side_characters,
            "initial_task": user_story.initial_task,
            "magic_elements": user_story.magic_elements,
            "obstacle": user_story.obstacle,
            "reward": user_story.reward,
            "cliffhanger_situation": user_story.cliffhanger_situation
        })
        
        # Analyze new elements
        new_elements, raw_elements_response = await summary_service.analyze_story_elements(
            recent_messages,
            existing_elements
        )
        
        # Update story with new summary and elements
        update_user_story(
            request.storyId,
            current_summary=new_summary
        )
        
        if new_elements:
            # Update with new elements
            update_dict = summary_service.update_story_data_from_analysis(
                {
                    "main_character_trait": user_story.main_character_trait,
                    "main_character_wish": user_story.main_character_wish,
                    "side_characters": user_story.side_characters,
                    "initial_task": user_story.initial_task,
                    "magic_elements": user_story.magic_elements,
                    "obstacle": user_story.obstacle,
                    "reward": user_story.reward,
                    "cliffhanger_situation": user_story.cliffhanger_situation
                },
                new_elements
            )
            
            update_story_summary_data(request.storyId, update_dict)
        
        return {
            "storyId": request.storyId,
            "updatedSummary": new_summary,
            "newElementsFound": new_elements is not None,
            "success": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize story: {str(e)}"
        )

async def summarize_story_background(
    story_id: str, 
    current_summary: str, 
    recent_messages: List[str],
    tale_title: str,
    summary_model: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    temperature: float = 0.7
):
    """Background task to summarize story and analyze elements"""
    try:
        # Get the user story
        user_story = get_user_story(story_id)
        if not user_story:
            return
        
        # Generate new summary
        new_summary, _ = await summary_service.generate_story_summary(
            current_summary,
            recent_messages,
            tale_title,
            model=summary_model,
            custom_prompt=custom_prompt,
            temperature=temperature
        )
        
        # Prepare existing elements for analysis
        existing_elements = summary_service.prepare_elements_for_analysis({
            "main_character_trait": user_story.main_character_trait,
            "main_character_wish": user_story.main_character_wish,
            "side_characters": user_story.side_characters,
            "initial_task": user_story.initial_task,
            "magic_elements": user_story.magic_elements,
            "obstacle": user_story.obstacle,
            "reward": user_story.reward,
            "cliffhanger_situation": user_story.cliffhanger_situation
        })
        
        # Analyze new elements
        new_elements, _ = await summary_service.analyze_story_elements(
            recent_messages,
            existing_elements,
            model=summary_model,
            temperature=temperature
        )
        
        # Update the story with new summary
        update_user_story(
            story_id,
            current_summary=new_summary
        )
        
        if new_elements:
            # Update with new elements
            update_dict = summary_service.update_story_data_from_analysis(
                {
                    "main_character_trait": user_story.main_character_trait,
                    "main_character_wish": user_story.main_character_wish,
                    "side_characters": user_story.side_characters,
                    "initial_task": user_story.initial_task,
                    "magic_elements": user_story.magic_elements,
                    "obstacle": user_story.obstacle,
                    "reward": user_story.reward,
                    "cliffhanger_situation": user_story.cliffhanger_situation
                },
                new_elements
            )
            
            update_story_summary_data(story_id, update_dict)
    except Exception as e:
        # Log but don't fail - this is a background task
        logger = logging.getLogger(__name__)
        logger.error(f"Error in background summarization for story {story_id}: {str(e)}")

@router.get("/stories/{story_id}", response_model=Dict[str, Any])
async def get_story_details(story_id: str):
    """Returns detailed information about a specific story"""
    try:
        # Get the user story
        user_story = get_user_story(story_id)
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Story with ID {story_id} not found"
            )
        
        # Get the base story
        base_story = get_base_story(user_story.base_story_id)
        if not base_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Base story not found"
            )
        
        # Prepare the response
        return {
            "id": user_story.id,
            "title": user_story.title,
            "baseStoryTitle": base_story.title,
            "currentTurnNumber": user_story.current_turn_number,
            "currentSummary": user_story.current_summary,
            "isCompleted": user_story.is_completed,
            "createdAt": user_story.created_at.isoformat(),
            "updatedAt": user_story.updated_at.isoformat(),
            "storyMessages": user_story.story_messages,
            "mainCharacter": user_story.main_character,
            "mainCharacterTrait": user_story.main_character_trait,
            "mainCharacterWish": user_story.main_character_wish,
            "sideCharacters": user_story.side_characters,
            "initialTask": user_story.initial_task,
            "magicElements": user_story.magic_elements,
            "obstacle": user_story.obstacle,
            "last_choices": user_story.last_choices or [],
            "reward": user_story.reward,
            "cliffhangerSituation": user_story.cliffhanger_situation,
            "setting": user_story.setting
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve story details: {str(e)}"
        )

@router.post("/stories/{story_id}/complete", response_model=Dict[str, Any])
async def mark_story_complete(story_id: str):
    """Marks a story as completed"""
    try:
        # Get the user story
        user_story = get_user_story(story_id)
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Story with ID {story_id} not found"
            )
        
        # Update the story
        update_user_story(story_id, is_completed=True)
        
        return {
            "id": story_id,
            "success": True,
            "message": "Story marked as completed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark story as complete: {str(e)}"
        )

@router.post("/stories/{story_id}/continue", response_model=Dict[str, Any])
async def continue_completed_story(story_id: str):
    """Continues a completed story, resetting turn counter but keeping context"""
    try:
        # Get the user story
        user_story = get_user_story(story_id)
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Story with ID {story_id} not found"
            )
        
        # Make sure the story was completed
        if not user_story.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot continue a story that isn't completed"
            )
        
        # Reset turn counter and completion status, but keep all context
        update_user_story(
            story_id, 
            is_completed=False,
            current_turn_number=1  # Start from turn 1
        )
        
        return {
            "id": story_id,
            "success": True,
            "message": "Story continuation enabled",
            "currentTurnNumber": 1
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to continue story: {str(e)}"
        )