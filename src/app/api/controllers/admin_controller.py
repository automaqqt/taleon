# --- START OF UPDATED controllers/admin_controller.py ---

import logging
from fastapi import APIRouter, HTTPException, Depends, Response, status, Body, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# Import necessary services and models
from ....services.summary_service import SummaryService
from ....models.database import BaseStory, StoryType, StoryPrompt, User # Import User directly
from ....database.db_utils import (
    # BaseStory related
    delete_base_story, get_db, create_base_story, get_base_story, get_all_base_stories,
    # StoryPrompt related
    create_story_prompt, delete_story_prompt, db_get_all_story_prompts,
    # StoryType related
    create_story_type, get_story_type, get_all_story_types, update_story_type, delete_story_type,
    assign_prompt_to_story_type, remove_prompt_from_story_type,
    # User/Auth related
    # REMOVE authenticate_user import here if only used for the dependency previously
    # Keep if used elsewhere
)
# Import password verification tool
from passlib.hash import bcrypt

logger = logging.getLogger(__name__)
summary_service = SummaryService() # Keep if used

# --- Pydantic Models ---

# Existing Models (BaseStoryRequest, StoryPromptRequest, AssignPromptRequest)
class BaseStoryRequest(BaseModel):
    """Request to create or update a base story"""
    story_type_id: str # Added
    title: str
    description: str
    original_tale_context: str
    initial_system_prompt: str
    initial_summary: str
    language: str = "Deutsch"

class StoryPromptRequest(BaseModel):
    """Request to create a story prompt (no assignment here)"""
    name: str
    system_prompt: str
    turn_start: int = 0
    turn_end: Optional[int] = None

# Removed AssignPromptRequest (replaced by AssignPromptToStoryTypeRequest)

# --- NEW Pydantic Models for StoryType ---

class StoryTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    initial_extraction_prompt: str
    dynamic_analysis_prompt: str
    summary_prompt: str

class StoryTypeCreateRequest(StoryTypeBase):
    pass

class StoryTypeUpdateRequest(StoryTypeBase):
    pass # All fields are updatable

class StoryPromptSimple(BaseModel): # For nested display
    id: str
    name: str
    turn_start: int
    turn_end: Optional[int] = None

    class Config:
        from_attributes = True

class StoryTypeDetailResponse(StoryTypeBase):
    id: str
    created_at: datetime
    updated_at: datetime
    story_prompts: List[StoryPromptSimple] = [] # Include assigned prompts

    class Config:
        from_attributes = True

class StoryTypeBasicResponse(BaseModel): # For list view
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

# --- NEW Pydantic Models for Prompt Assignment ---

class AssignPromptToStoryTypeRequest(BaseModel):
    prompt_id: str
    story_type_id: str

# --- Authentication Dependency ---
# Using Basic Auth for simplicity, align with auth.js
security = HTTPBasic()

async def get_current_admin_user(credentials: HTTPBasicCredentials = Depends(security)) -> User:
    """
    Dependency that authenticates based on Basic Auth credentials
    and returns the admin User object if valid. Manages its own DB session.
    """
    # Use the get_db context manager *within* the dependency
    with get_db() as db:
        user = db.query(User).filter(User.username == credentials.username).first()

        # 1. Check if user exists and password is correct
        if not user or not bcrypt.verify(credentials.password, user.password_hash):
            logger.warning(f"Admin authentication failed for user: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"},
            )

        # 2. Check if the user is an admin *while the session is active*
        if not user.is_admin:
            logger.warning(f"Admin access denied for non-admin user: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, # Use 403 for insufficient permissions
                detail="User does not have admin privileges",
                # No WWW-Authenticate header needed for 403
            )

        # 3. (Optional but recommended) Update last login time
        try:
            user.last_login = datetime.utcnow()
            db.commit()
            logger.info(f"Admin access granted and last_login updated for user: {user.username}")
        except Exception as e:
            logger.error(f"Failed to update last_login for user {user.username}: {e}")
            db.rollback()
            # Decide if this failure should prevent login? Probably not critical.

        # 4. Return the user object *before* the session closes
        # The object is still attached to the session at this point
        return user
    # --- Session closes here when 'with' block exits ---


# --- Create Router ---
router = APIRouter(
    prefix="/admin", # Add prefix for all admin routes
    tags=["Admin"], # Group in Swagger UI
    dependencies=[Depends(get_current_admin_user)] # Apply auth to all routes in this router
)

# === StoryType Endpoints ===

@router.post("/story-types", response_model=StoryTypeBasicResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_story_type(request: StoryTypeCreateRequest):
    """Creates a new Story Type (admin only)"""
    try:
        story_type = create_story_type(
            name=request.name,
            description=request.description,
            initial_extraction_prompt=request.initial_extraction_prompt,
            dynamic_analysis_prompt=request.dynamic_analysis_prompt,
            summary_prompt=request.summary_prompt
        )
        return story_type
    except Exception as e:
        logger.exception(f"Failed to create story type: {request.name}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/story-types", response_model=List[StoryTypeBasicResponse])
async def admin_get_all_story_types():
    """Lists all available Story Types (admin only)"""
    try:
        story_types = get_all_story_types()
        return story_types # Pydantic handles conversion
    except Exception as e:
        logger.exception("Failed to retrieve story types")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/story-types/{story_type_id}", response_model=StoryTypeDetailResponse)
async def admin_get_story_type_details(story_type_id: str):
    """Gets details of a specific Story Type, including assigned prompts (admin only)"""
    try:
        story_type = get_story_type(story_type_id)
        if not story_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story Type not found")
        # The response model will automatically serialize based on relationships if configured
        return story_type
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve story type details for {story_type_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/story-types/{story_type_id}", response_model=StoryTypeBasicResponse)
async def admin_update_story_type(story_type_id: str, request: StoryTypeUpdateRequest):
    """Updates an existing Story Type (admin only)"""
    try:
        updated_type = update_story_type(story_type_id, **request.dict())
        if not updated_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story Type not found")
        return updated_type
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update story type {story_type_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/story-types/{story_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_story_type_endpoint(story_type_id: str):
    """Deletes a Story Type if no Base Stories depend on it (admin only)"""
    success, message = delete_story_type(story_type_id)
    if not success:
        if "not found" in message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        elif "depend on it" in message:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# === BaseStory Endpoints (Modified Create/Update) ===

# Note: create_base_story is now async in db_utils
@router.post("/base-stories", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def admin_create_base_story(request: BaseStoryRequest):
    """Creates a new base story template linked to a Story Type (admin only)"""
    logger.info(f"Received request to create base story: {request.title} for type {request.story_type_id}")
    try:
        # Call the async db_util function
        base_story = await create_base_story(
            story_type_id=request.story_type_id,
            title=request.title,
            description=request.description,
            original_tale_context=request.original_tale_context,
            initial_system_prompt=request.initial_system_prompt,
            initial_summary=request.initial_summary,
            language=request.language
        )
        if not base_story:
             # This could happen if story_type_id is invalid
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Story Type ID: {request.story_type_id} or other creation error.")

        return {
            "id": base_story.id,
            "title": base_story.title,
            "description": base_story.description,
            "story_type_id": base_story.story_type_id,
            "initial_elements_extracted": base_story.initial_story_elements is not None,
            "success": True # Keep success flag for frontend if useful
        }
    except HTTPException:
        raise # Re-raise specific HTTP exceptions
    except Exception as e:
        logger.exception(f"Failed to create base story: {request.title}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create base story: {str(e)}")

@router.put("/base-stories/{story_id}", response_model=Dict[str, Any])
async def admin_update_base_story(story_id: str, request: BaseStoryRequest):
    """Updates an existing base story (admin only)"""
    # Note: If initial analysis should be re-run on context change, this needs adjustment
    try:
        # Simple update using setattr in db_utils or direct update here
        with get_db() as db:
            base_story = db.query(BaseStory).filter(BaseStory.id == story_id).first()
            if not base_story:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Base Story not found")

            # Update fields from request
            base_story.story_type_id = request.story_type_id # Allow changing type
            base_story.title = request.title
            base_story.description = request.description
            # Check if context changed to potentially re-run initial analysis? Optional.
            # if base_story.original_tale_context != request.original_tale_context:
            #    logger.info("Original context changed, re-running initial analysis...")
            #    # Need to call the async analysis here, making this endpoint async
            #    analysis_result, _ = await summary_service._analyze_initial_context(...)
            #    base_story.initial_story_elements = analysis_result
            base_story.original_tale_context = request.original_tale_context
            base_story.initial_system_prompt = request.initial_system_prompt
            base_story.initial_summary = request.initial_summary
            base_story.language = request.language

            db.commit()
            db.refresh(base_story)

        return {
            "id": base_story.id,
            "title": base_story.title,
            "description": base_story.description,
            "story_type_id": base_story.story_type_id,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update base story {story_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update base story: {str(e)}")

@router.get("/base-stories/{story_id}", response_model=Dict[str, Any])
async def admin_get_base_story_details(story_id: str):
    """Get detailed information about a base story (admin only)"""
    # This needs adjustment to return story_type info and remove prompts
    try:
        with get_db() as db:
            # Eager load story type
            from sqlalchemy.orm import joinedload
            base_story = db.query(BaseStory).options(joinedload(BaseStory.story_type)).filter(BaseStory.id == story_id).first()
            if not base_story:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Base story with ID {story_id} not found")

            story_type_info = None
            if base_story.story_type:
                 story_type_info = {
                     "id": base_story.story_type.id,
                     "name": base_story.story_type.name
                 }

            return {
                "id": base_story.id,
                "title": base_story.title,
                "description": base_story.description,
                "original_tale_context": base_story.original_tale_context,
                "initial_system_prompt": base_story.initial_system_prompt,
                "initial_summary": base_story.initial_summary,
                "language": base_story.language,
                "is_active": base_story.is_active,
                "created_at": base_story.created_at.isoformat(),
                "updated_at": base_story.updated_at.isoformat(),
                "initial_story_elements": base_story.initial_story_elements or {},
                "story_type": story_type_info, # Include linked story type info
                "story_type_id": base_story.story_type_id # Explicitly include ID
                # Removed "story_prompts"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve base story details for {story_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/base-stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_base_story_endpoint(story_id: str):
    """Deletes a base story if no user stories depend on it (admin only)"""
    # ... (keep existing implementation using db_utils.delete_base_story) ...
    logger.info(f"Received request to delete base story ID: {story_id}")
    try:
        success, message = delete_base_story(story_id)
        if not success:
            if "not found" in message: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
            elif "user stories depend on it" in message: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
            else: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException: raise
    except Exception as e: logger.exception(f"API Error: Unexpected error deleting base story {story_id}."); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/toggle-base-story/{story_id}", response_model=Dict[str, Any])
async def admin_toggle_base_story(story_id: str, active: bool = Body(..., embed=True)): # Get active from body
    """Toggles a base story's active status (admin only)"""
    # ... (keep existing implementation) ...
    try:
        with get_db() as db:
            base_story = db.query(BaseStory).filter(BaseStory.id == story_id).first()
            if not base_story: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Base story with ID {story_id} not found")
            base_story.is_active = active
            db.commit()
            db.refresh(base_story)
        return {"id": base_story.id, "is_active": base_story.is_active, "success": True}
    except HTTPException: raise
    except Exception as e: logger.exception(f"Failed to toggle base story {story_id}"); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to toggle base story status: {str(e)}")


# === StoryPrompt Endpoints ===

@router.post("/story-prompts", response_model=StoryPromptSimple, status_code=status.HTTP_201_CREATED)
async def admin_create_story_prompt(request: StoryPromptRequest):
    """Creates a new Story Prompt (unassigned) (admin only)"""
    try:
        prompt = create_story_prompt(
            name=request.name,
            system_prompt=request.system_prompt,
            turn_start=request.turn_start,
            turn_end=request.turn_end
        )
        return prompt # Return the created prompt using StoryPromptSimple model
    except Exception as e:
        logger.exception(f"Failed to create story prompt: {request.name}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# NEW endpoint to get all prompts
@router.get("/story-prompts/all", response_model=List[StoryPromptSimple])
async def admin_get_all_prompts():
    """Lists all available Story Prompts (admin only)"""
    try:
        prompts = db_get_all_story_prompts() # Need to implement this in db_utils
        return prompts
    except Exception as e:
        logger.exception("Failed to retrieve all story prompts")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/story-prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_story_prompt_endpoint(prompt_id: str):
    """Deletes a story prompt (admin only)"""
    # ... (keep existing implementation using db_utils.delete_story_prompt) ...
    logger.info(f"Received request to delete story prompt ID: {prompt_id}")
    try:
        success, message = delete_story_prompt(prompt_id)
        if not success:
            if "not found" in message: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
            else: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException: raise
    except Exception as e: logger.exception(f"API Error: Unexpected error deleting story prompt {prompt_id}."); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")


# === Prompt Assignment Endpoints ===

@router.post("/story-types/assign-prompt", response_model=Dict[str, bool])
async def admin_assign_prompt_to_type(request: AssignPromptToStoryTypeRequest):
    """Assigns an existing prompt to a Story Type (admin only)"""
    success = assign_prompt_to_story_type(
        prompt_id=request.prompt_id,
        story_type_id=request.story_type_id
    )
    if not success:
        # db_utils function logs details, check logs for reason (404 or other)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to assign prompt. Check if prompt and story type exist and are not already linked.")
    return {"success": True}

@router.delete("/story-types/{story_type_id}/prompts/{prompt_id}", response_model=Dict[str, bool])
async def admin_remove_prompt_from_type_endpoint(story_type_id: str, prompt_id: str):
    """Removes a prompt assignment from a Story Type (admin only)"""
    # Need to implement remove_prompt_from_story_type in db_utils
    success = remove_prompt_from_story_type(prompt_id=prompt_id, story_type_id=story_type_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to remove prompt assignment. Check if the assignment exists.")
    return {"success": True}


# === REMOVED Endpoints ===
# Removed /admin/assign-prompt (replaced by /admin/story-types/assign-prompt)

# --- END OF UPDATED controllers/admin_controller.py ---