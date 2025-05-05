
# --- START OF FILE controllers/story_controller.py ---

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

# Assuming db_utils and services are in paths relative to this controller's location
from ....database.db_utils import (
    get_db, get_all_base_stories, get_base_story, create_user_story, get_story_type,
    get_user_story, get_user_stories, update_user_story, add_story_message,
    get_story_prompts_for_turn, update_story_summary_data, # Keep update_story_summary_data for now
    StoryType, BaseStory, UserStory # Import models for type hinting
)
from ....services.story_service import StoryService, DEFAULT_TEMPERATURE
from ....services.summary_service import SummaryService
from ....models.database import flag_modified # Import flag_modified if needed directly

logger = logging.getLogger(__name__)

# --- Initialize Services ---
story_service = StoryService()
summary_service = SummaryService()

# --- Pydantic Models (Keep existing models: StoryAction, DebugConfig, etc.) ---
# ... (StoryAction, DebugConfig, GenerateSegmentRequest, ListStoriesRequest, CreateStoryRequest, SummarizeStoryRequest, StoryResponse, StoryMetadata)


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


# Modify UserStoryDetailResponse to reflect new structure (remove individual fields)
class UserStoryDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    user_id: str
    base_story_id: str
    baseStoryTitle: Optional[str] = None # Keep for convenience
    storyTypeId: Optional[str] = None # Add StoryType ID
    storyTypeName: Optional[str] = None # Add StoryType Name
    currentSummary: Optional[str] = None
    currentTurnNumber: int
    isCompleted: bool
    storyMessages: List[Dict[str, Any]] = []
    last_choices: Optional[List[str]] = None
    story_context: Dict[str, Any] = {} # Add the context field
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    class Config:
        from_attributes = True # Pydantic v2 style

# --- Router Setup ---
router = APIRouter()

# --- Endpoints ---

# GET /base-stories (No change needed structurally)
@router.get("/base-stories", response_model=List[Dict[str, Any]])
async def get_available_base_stories():
    """Returns a list of available base stories that users can start from"""
    try:
        base_stories = get_all_base_stories()
        formatted_stories = []
        for story in base_stories:
            # Optionally fetch story_type name if needed here
            story_type_name = story.story_type.name if story.story_type else "Unknown Type"
            formatted_stories.append({
                "id": story.id,
                "title": story.title,
                "description": story.description,
                "language": story.language,
                "is_active": story.is_active,
                "storyTypeName": story_type_name # Add type name
            })
        return formatted_stories
    except Exception as e:
        logger.exception("Failed to retrieve base stories")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve base stories")


# POST /stories (No change needed, create_user_story handles new logic)
@router.post("/stories", response_model=Dict[str, Any])
async def create_new_story(request: CreateStoryRequest):
    """Creates a new user story based on a base story"""
    try:
        # create_user_story in db_utils now handles initializing context
        user_story = create_user_story(
            user_id=request.userId,
            base_story_id=request.baseStoryId,
            title=request.title # Optional title remains
        )
        if not user_story:
             # Base story not found likely
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Base story with ID {request.baseStoryId} not found")

        # Fetch base story title for response
        base_story = get_base_story(request.baseStoryId) # Assumes it exists if user_story was created
        base_title = base_story.title if base_story else "Unknown"

        return {
            "id": user_story.id,
            "title": user_story.title,
            "baseStoryTitle": base_title,
            "currentTurnNumber": user_story.current_turn_number,
            "currentSummary": user_story.current_summary,
            "isCompleted": user_story.is_completed,
            "createdAt": user_story.created_at.isoformat(),
            "updatedAt": user_story.updated_at.isoformat(),
            "story_context": user_story.story_context # Include initial context
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create story for user {request.userId}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create story: {str(e)}")

# GET /stories (No change needed structurally)
@router.get("/stories", response_model=List[StoryMetadata])
async def list_user_stories(userId: str, includeCompleted: bool = False):
    """Returns a list of stories for a user"""
    try:
        user_stories = get_user_stories(userId, completed=None if includeCompleted else False)
        stories_list = []
        for story in user_stories:
            # Fetch base story title efficiently if possible (maybe store on UserStory or join)
            base_title = story.base_story.title if story.base_story else "Unknown Base"
            stories_list.append(
                StoryMetadata( # Use the Pydantic model directly
                    id=story.id,
                    title=story.title,
                    currentTurnNumber=story.current_turn_number,
                    baseStoryTitle=base_title,
                    isCompleted=story.is_completed,
                    updatedAt=story.updated_at.isoformat(),
                    createdAt=story.created_at.isoformat()
                )
            )
        return stories_list
    except Exception as e:
        logger.exception(f"Failed to retrieve stories for user {userId}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve stories")

# --- !!! MAJOR REFACTOR: POST /generate-segment !!! ---
@router.post("/generate-segment", response_model=StoryResponse)
async def generate_story_segment(request: GenerateSegmentRequest, background_tasks: BackgroundTasks):
    """Generates the next story segment based on user action and context"""
    user_story: Optional[UserStory] = None # Initialize for broader scope

    try:
        # --- 1. Fetch Core Objects ---
        user_story = get_user_story(request.storyId)
        if not user_story:
            logger.warning(f"Story not found for ID: {request.storyId}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Story {request.storyId} not found")

        # Access related objects (SQLAlchemy lazy loads them if not eager loaded)
        base_story: Optional[BaseStory] = user_story.base_story
        if not base_story:
             logger.error(f"Data inconsistency: UserStory {request.storyId} has no associated BaseStory (ID: {user_story.base_story_id}).")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Story data is inconsistent (missing base story).")

        story_type: Optional[StoryType] = base_story.story_type
        if not story_type:
             logger.error(f"Data inconsistency: BaseStory {base_story.id} has no associated StoryType (ID: {base_story.story_type_id}).")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Story data is inconsistent (missing story type).")

        logger.info(f"Generating segment for Story '{user_story.title}' (ID: {request.storyId}), Turn: {request.currentTurnNumber}, Type: '{story_type.name}'")

        # --- 2. Validate Turn Number ---
        # Ensure the request's turn matches the story's current turn
        if request.currentTurnNumber != user_story.current_turn_number:
            logger.warning(f"Turn number mismatch for story {request.storyId}. Expected {user_story.current_turn_number}, got {request.currentTurnNumber}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, # 409 Conflict is suitable here
                detail=f"Turn number mismatch. Expected {user_story.current_turn_number}, but request is for {request.currentTurnNumber}. Please refresh."
            )

        # --- 3. Format User Action and Add to History ---
        if request.action is None or (request.action.choice is None and request.action.customInput is None):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No action (choice or customInput) provided.")

        formatted_action = story_service.format_user_action(request.action.dict(exclude_none=True))
        # Use the utility function to add the message (handles JSON update)
        add_story_message(
            request.storyId,
            "userInput" if request.action.customInput else "choice",
            formatted_action,
            user_story.current_turn_number # Action happens *at* the current turn
        )
        # Fetch the updated story messages list for history preparation
        # (get_user_story might need refreshing if add_story_message doesn't update the object in memory)
        # Re-fetch or rely on add_story_message potentially returning the updated story
        # For safety, let's assume we need the list directly:
        current_messages = get_user_story(request.storyId).story_messages or [] # Re-fetch if needed
        story_history_texts = [msg.get("content", "") for msg in current_messages]


        # --- 4. Select System Prompt ---
        system_prompt_text: Optional[str] = None
        prompt_source: str = "None"

        # Use debug prompt if provided
        if request.debugConfig and request.debugConfig.systemPrompt:
            system_prompt_text = request.debugConfig.systemPrompt
            prompt_source = "DebugConfig"
            logger.debug(f"Using debug system prompt for story {request.storyId}")
        else:
            # Find prompt based on turn number and story type
            valid_prompts = get_story_prompts_for_turn(story_type.id, user_story.current_turn_number)
            if valid_prompts:
                system_prompt_text = valid_prompts[0].system_prompt # Highest priority one
                prompt_source = f"StoryType Prompt (Turn >= {valid_prompts[0].turn_start})"
                logger.debug(f"Using prompt '{valid_prompts[0].name}' defined for turn >= {valid_prompts[0].turn_start} from StoryType '{story_type.name}'.")
            # Removed fallback to base_story.initial_system_prompt here based on refined flow.
            # If no prompt is found via StoryType, it's a configuration error.

        if not system_prompt_text:
            logger.error(f"No system prompt could be determined for StoryType '{story_type.name}' (ID: {story_type.id}), turn {user_story.current_turn_number}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Story configuration error: Cannot determine system prompt for story generation at this turn."
            )

        # --- 5. Prepare Context for Injection ---
        # Context comes from: user_story.story_context, base_story.initial_story_elements, current_summary, original_tale_context, other direct fields
        other_context_fields = {
            "current_turn_number": user_story.current_turn_number,
            "language": base_story.language,
            "base_story_title": base_story.title,
            "last_choices": user_story.last_choices or [] # Pass previous choices
            # Add any other direct fields that might be useful placeholders
        }

        # Call the injection service function
        try:
            injected_prompt = story_service._inject_context_into_prompt(
                system_prompt=system_prompt_text,
                user_story_context=user_story.story_context or {}, # Pass dynamic context
                base_story_elements=base_story.initial_story_elements or {}, # Pass initial context
                current_summary=user_story.current_summary or "",
                original_tale_context=base_story.original_tale_context or "",
                other_fields=other_context_fields
            )
        except Exception as inject_err:
            logger.exception(f"Error during context injection for story {request.storyId}")
            # Decide: fail request or try with un-injected prompt? Let's fail for now.
            raise HTTPException(status_code=500, detail=f"Internal error during prompt preparation: {inject_err}")


        # --- 6. Get LLM Configuration ---
        story_model = request.debugConfig.storyModel if request.debugConfig and request.debugConfig.storyModel else None # Service uses its default if None
        temperature = request.debugConfig.temperature if request.debugConfig and request.debugConfig.temperature is not None else DEFAULT_TEMPERATURE

        # --- 7. Generate the Story Segment ---
        llm_response_data, raw_response = await story_service.generate_story_segment(
            injected_system_prompt=injected_prompt, # Pass the fully prepared prompt
            history=story_history_texts, # Pass list of message contents
            model=story_model,
            temperature=temperature
        )

        if not llm_response_data:
            logger.error(f"Failed to generate/parse story segment for story {request.storyId}. Prompt source: {prompt_source}. Raw response: {raw_response}")
            # Provide more specific error based on raw_response if possible
            error_detail = "Failed to generate story segment. LLM response issue."
            if raw_response and "API Error:" in raw_response:
                 error_detail = f"LLM API Error: {raw_response.split('API Error:', 1)[1].strip()}"
            elif raw_response and "Unexpected Server Error:" in raw_response:
                  error_detail = f"Internal Error during LLM call: {raw_response.split('Unexpected Server Error:', 1)[1].strip()}"

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            )

        # --- 8. Add Generated Segment to History ---
        generated_segment_text = llm_response_data["storySegment"]
        add_story_message(
            request.storyId,
            "story",
            generated_segment_text,
            user_story.current_turn_number # Segment belongs to the turn just completed
        )

        # --- 9. Prepare for Next Turn & Update Story State ---
        next_turn_number = user_story.current_turn_number + 1
        next_choices = llm_response_data.get("choices", []) # Get choices from LLM response

        updated_story = update_user_story(
            request.storyId,
            current_turn_number=next_turn_number,
            last_choices=next_choices # Save the choices for the *next* turn
        )

        if not updated_story:
             # This really shouldn't happen if we fetched it earlier
             logger.error(f"Critical error: Failed to find story {request.storyId} during final update.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save story state after generation.")

        # --- 10. Trigger Background Tasks (Analysis & Summary) ---
        current_turn_completed = user_story.current_turn_number # The turn number that *was just* completed

        # Dynamic Analysis Trigger (runs every 3 turns, AFTER turn 0)
        if current_turn_completed > 0 and current_turn_completed % 2 == 0:
            logger.info(f"Triggering background dynamic analysis for story {request.storyId} after turn {current_turn_completed}")
            history_for_analysis = story_history_texts + [generated_segment_text] # Include latest segment
            background_tasks.add_task(
                analyze_story_dynamically, # New background task function
                story_id=request.storyId,
                story_type_id=story_type.id, # Pass type ID to get correct prompt
                recent_messages_content=history_for_analysis[-6:], # Pass last ~3 interactions
                analysis_model=(request.debugConfig.summaryModel if request.debugConfig else None) # Reuse summary model for now
            )

        # Summary Trigger
        if story_service.should_trigger_summary(current_turn_completed): # Check based on completed turn
            logger.info(f"Triggering background summarization for story {request.storyId} after turn {current_turn_completed}")
            history_for_summary = story_history_texts + [generated_segment_text] # Include latest segment
            background_tasks.add_task(
                summarize_story_background, # Existing background task function
                story_id=request.storyId,
                story_type_id=story_type.id, # Pass type ID to get correct prompt
                current_summary=user_story.current_summary or "", # Pass current summary
                recent_messages_content=history_for_summary[-10:], # Pass recent messages
                summary_model=(request.debugConfig.summaryModel if request.debugConfig else None),
                debug_summary_prompt=(request.debugConfig.summarySystemPrompt if request.debugConfig else None),
                temperature=temperature # Can potentially use a different temp for summary
            )

        # --- 11. Prepare and Return Response ---
        response = StoryResponse(
            storySegment=generated_segment_text,
            choices=next_choices,
            # Return the summary *before* the background task runs
            updatedSummary=user_story.current_summary or "",
            nextTurnNumber=next_turn_number,
            storyId=request.storyId,
            rawResponse=raw_response if request.debugConfig else None, # Only include if debugging
            errorMessage=None
        )
        logger.info(f"Successfully generated segment for story {request.storyId}, next turn is {next_turn_number}")
        return response

    except HTTPException as he:
        # Log and re-raise known HTTP errors
        log_level = logging.ERROR if (he.status_code >= 500) else logging.WARNING
        logger.log(log_level, f"HTTPException in generate_story_segment for story {request.storyId or 'UNKNOWN'}: {he.status_code} - {he.detail}")
        raise he

    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error generating story segment for story {request.storyId or 'UNKNOWN'}")

        # Attempt to provide a graceful fallback response (optional)
        # current_turn = user_story.current_turn_number if user_story else request.currentTurnNumber
        # current_summary = user_story.current_summary if user_story else ""
        # return StoryResponse(...) with error message

        # Or just raise a generic 500
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected server error occurred.")


# POST /summarize (Manual Trigger - Keep as is, but use StoryType prompt)
@router.post("/summarize", response_model=Dict[str, Any])
async def summarize_story(request: SummarizeStoryRequest):
    """Trigger a manual summary update for a story"""
    try:
        user_story = get_user_story(request.storyId)
        if not user_story:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Story {request.storyId} not found")
        if not user_story.base_story or not user_story.base_story.story_type:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Story data inconsistent (missing base/type)")

        story_type = user_story.base_story.story_type
        story_history = user_story.story_messages or []
        recent_messages = [msg["content"] for msg in story_history[-10:]] # Get last 10 message contents

        new_summary, _ = await summary_service.generate_story_summary(
            system_prompt=story_type.summary_prompt, # Use prompt from StoryType
            existing_summary=user_story.current_summary or "",
            recent_developments=recent_messages
            # Model/temp defaults used unless passed via debug config in a real scenario
        )

        # Update the story summary
        update_user_story(request.storyId, current_summary=new_summary)

        # Manual trigger probably doesn't need to re-run analysis,
        # but you could add it here if desired.

        return {
            "storyId": request.storyId,
            "updatedSummary": new_summary,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to manually summarize story {request.storyId}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to summarize story: {str(e)}")


# --- Background Tasks ---

async def analyze_story_dynamically(
    story_id: str,
    story_type_id: str,
    recent_messages_content: List[str],
    analysis_model: Optional[str] = None
    # Add temperature if needed
):
    """Background task to perform dynamic analysis and update story_context."""
    logger.info(f"BACKGROUND: Starting dynamic analysis for story {story_id}")
    try:
        # 1. Fetch necessary data
        user_story = get_user_story(story_id)
        story_type = get_story_type(story_type_id) # Fetch StoryType using its ID

        if not user_story:
            logger.error(f"BACKGROUND ANALYSIS: UserStory {story_id} not found. Aborting.")
            return
        if not story_type:
             logger.error(f"BACKGROUND ANALYSIS: StoryType {story_type_id} not found for Story {story_id}. Aborting.")
             return

        # 2. Prepare existing context for analysis
        existing_context_for_prompt = summary_service.prepare_elements_for_analysis(
            user_story.story_context or {}
        )

        # 3. Call analysis service
        analysis_results, _ = await summary_service.analyze_story_elements(
            system_prompt=story_type.dynamic_analysis_prompt, # Use the correct prompt
            recent_texts=recent_messages_content,
            existing_elements=existing_context_for_prompt,
            model=analysis_model # Pass model if provided
            # Add temperature if needed
        )

        if not analysis_results:
            logger.warning(f"BACKGROUND ANALYSIS: Analysis returned no results for story {story_id}.")
            return

        # 4. Merge results into existing context
        merged_context = summary_service.update_story_data_from_analysis(
            existing_context=user_story.story_context or {},
            analysis_results=analysis_results
        )

        # 5. Update the user story with the merged context
        if merged_context != (user_story.story_context or {}): # Check if context actually changed
            logger.info(f"BACKGROUND ANALYSIS: Updating story_context for story {story_id}.")
            update_user_story(story_id, story_context=merged_context)
        else:
            logger.info(f"BACKGROUND ANALYSIS: No changes detected in story_context for story {story_id}.")

    except Exception as e:
        logger.exception(f"BACKGROUND ANALYSIS: Error during dynamic analysis for story {story_id}: {e}")
        # Don't raise, just log the error for background tasks


async def summarize_story_background(
    story_id: str,
    story_type_id: str,
    current_summary: str,
    recent_messages_content: List[str],
    summary_model: Optional[str] = None,
    debug_summary_prompt: Optional[str] = None, # Renamed for clarity
    temperature: float = DEFAULT_TEMPERATURE # Use story temp or dedicated summary temp
):
    """Background task to update story summary."""
    logger.info(f"BACKGROUND: Starting summarization for story {story_id}")
    try:
        # 1. Fetch StoryType to get the correct prompt (unless overridden by debug)
        system_prompt_to_use = debug_summary_prompt # Prioritize debug prompt
        if not system_prompt_to_use:
            story_type = get_story_type(story_type_id)
            if not story_type:
                 logger.error(f"BACKGROUND SUMMARY: StoryType {story_type_id} not found for Story {story_id}. Cannot get summary prompt.")
                 return
            system_prompt_to_use = story_type.summary_prompt

        if not system_prompt_to_use:
             logger.error(f"BACKGROUND SUMMARY: No summary prompt available (debug or from StoryType {story_type_id}) for Story {story_id}.")
             return

        # 2. Generate new summary
        new_summary, _ = await summary_service.generate_story_summary(
            system_prompt=system_prompt_to_use,
            existing_summary=current_summary,
            recent_developments=recent_messages_content,
            model=summary_model,
            temperature=temperature
        )

        # 3. Update the story only if the summary changed
        if new_summary != current_summary:
             logger.info(f"BACKGROUND SUMMARY: Updating summary for story {story_id}.")
             update_user_story(
                 story_id,
                 current_summary=new_summary
             )
        else:
             logger.info(f"BACKGROUND SUMMARY: Summary unchanged for story {story_id}.")

    except Exception as e:
        logger.exception(f"BACKGROUND SUMMARY: Error during background summarization for story {story_id}: {e}")


# GET /stories/{story_id} (Modified to use new response model)
@router.get("/stories/{story_id}", response_model=UserStoryDetailResponse)
async def get_story_details(story_id: str):
    """Returns detailed information about a specific story"""
    try:
        user_story = get_user_story(story_id) # Assumes get_user_story eager loads or handles related data access
        if not user_story:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Story {story_id} not found")

        # Prepare response data
        base_title = user_story.base_story.title if user_story.base_story else "Unknown Base"
        story_type_id = user_story.base_story.story_type_id if user_story.base_story else None
        story_type_name = user_story.base_story.story_type.name if user_story.base_story and user_story.base_story.story_type else "Unknown Type"

        # Create response using the Pydantic model
        response_data = UserStoryDetailResponse(
            id=user_story.id,
            title=user_story.title,
            user_id=user_story.user_id,
            base_story_id=user_story.base_story_id,
            baseStoryTitle=base_title,
            storyTypeId=story_type_id,
            storyTypeName=story_type_name,
            currentSummary=user_story.current_summary,
            currentTurnNumber=user_story.current_turn_number,
            isCompleted=user_story.is_completed,
            storyMessages=user_story.story_messages or [],
            last_choices=user_story.last_choices or [],
            story_context=user_story.story_context or {},
            createdAt=user_story.created_at,
            updatedAt=user_story.updated_at
        )
        return response_data # FastAPI handles serialization

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve details for story {story_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve story details")


# POST /stories/{story_id}/complete (No change needed)
@router.post("/stories/{story_id}/complete", response_model=Dict[str, Any])
async def mark_story_complete(story_id: str):
    """Marks a story as completed"""
    # ... (keep existing implementation)
    try:
        updated = update_user_story(story_id, is_completed=True)
        if not updated:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Story {story_id} not found")
        return {"id": story_id, "success": True, "message": "Story marked as completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to mark story {story_id} complete")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to mark story complete")


# POST /stories/{story_id}/continue (No change needed)
@router.post("/stories/{story_id}/continue", response_model=Dict[str, Any])
async def continue_completed_story(story_id: str):
    """Continues a completed story"""
    # ... (keep existing implementation)
    try:
        user_story = get_user_story(story_id)
        if not user_story:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Story {story_id} not found")
        if not user_story.is_completed:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Story is not completed")

        updated = update_user_story(story_id, is_completed=False, current_turn_number=user_story.current_turn_number) # Keep current turn? Or reset? Let's keep.
        if not updated:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update story state")

        return {"id": story_id, "success": True, "message": "Story continuation enabled", "currentTurnNumber": updated.current_turn_number}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to continue story {story_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to continue story")


# --- END OF FILE controllers/story_controller.py ---