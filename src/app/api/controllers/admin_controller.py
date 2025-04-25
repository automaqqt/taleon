import logging
from fastapi import APIRouter, HTTPException, Depends, Response, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from ....services.summary_service import SummaryService
logger = logging.getLogger(__name__)
from ....models.database import BaseStory

from ....database.db_utils import (
    delete_base_story, delete_story_prompt, get_db, create_base_story, get_base_story, get_all_base_stories,
    create_story_prompt, assign_prompt_to_base_story,
    authenticate_user
)

# Define Pydantic models for request/response
class BaseStoryRequest(BaseModel):
    """Request to create or update a base story"""
    title: str
    description: str
    original_tale_context: str
    initial_system_prompt: str
    initial_summary: str
    language: str = "Deutsch"

class StoryPromptRequest(BaseModel):
    """Request to create or update a story prompt"""
    name: str
    system_prompt: str
    turn_start: int = 0
    turn_end: Optional[int] = None
    base_story_id: Optional[str] = None

class AssignPromptRequest(BaseModel):
    """Request to assign a prompt to a base story"""
    prompt_id: str
    base_story_id: str

class AuthRequest(BaseModel):
    """Request for authentication"""
    username: str
    password: str

summary_service = SummaryService()

# Admin-only dependency
async def admin_only(auth: AuthRequest):
    """Dependency to ensure only admins can access endpoints"""
    user = authenticate_user(auth.username, auth.password)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user

# Create router
router = APIRouter()

@router.post("/admin/base-stories", response_model=Dict[str, Any])
async def admin_create_base_story(request: BaseStoryRequest):
    """Creates a new base story template (admin only)"""
    # Authenticate admin
    print(request)
    logger.info(f"Analyzing initial context for new base story: {request.title}")
    extracted_elements = await summary_service._analyze_initial_context(request.original_tale_context)

    if extracted_elements:
        logger.info("Initial context analysis successful.")
        # Optional: Validate extracted_elements schema here if needed
    else:
        logger.warning(f"Could not extract initial elements for base story '{request.title}'. Proceeding without them.")
        extracted_elements = None # Ensure it's None if analysis failed

    # --- 2. Create the base story in DB ---
    try:
        base_story = create_base_story(
            title=request.title,
            description=request.description,
            original_tale_context=request.original_tale_context,
            initial_system_prompt=request.initial_system_prompt,
            initial_summary=request.initial_summary,
            language=request.language,
            initial_story_elements=extracted_elements # Pass the extracted data
        )
        logger.info(f"Successfully created base story with ID: {base_story.id}")

        return {
            "id": base_story.id,
            "title": base_story.title,
            "description": base_story.description,
            "initial_elements_extracted": extracted_elements is not None,
            "success": True
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create base story: {str(e)}"
        )

@router.post("/admin/story-prompts", response_model=Dict[str, Any])
async def admin_create_story_prompt(request: StoryPromptRequest):
    """Creates a new story prompt (admin only)"""
    # Authenticate admin
    
    try:
        prompt = create_story_prompt(
            name=request.name,
            system_prompt=request.system_prompt,
            turn_start=request.turn_start,
            turn_end=request.turn_end
        )
        
        # If a base_story_id is provided, assign the prompt to that story
        print(request)
        if hasattr(request, 'base_story_id') and request.base_story_id:
            success = assign_prompt_to_base_story(
                prompt_id=prompt.id,
                base_story_id=request.base_story_id
            )
            if not success:
                # We created the prompt but couldn't assign it - still return success
                # but with a note
                return {
                    "id": prompt.id,
                    "name": prompt.name,
                    "turn_start": prompt.turn_start,
                    "turn_end": prompt.turn_end,
                    "success": True,
                    "assignment_success": False,
                    "message": "Prompt created but could not be assigned to story"
                }
        
        return {
            "id": prompt.id,
            "name": prompt.name,
            "turn_start": prompt.turn_start,
            "turn_end": prompt.turn_end,
            "success": True,
            "assignment_success": hasattr(request, 'base_story_id') and request.base_story_id is not None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create story prompt: {str(e)}"
        )

@router.post("/admin/assign-prompt", response_model=Dict[str, bool])
async def admin_assign_prompt(request: AssignPromptRequest):
    """Assigns a prompt to a base story (admin only)"""
    # Authenticate admin
    
    try:
        success = assign_prompt_to_base_story(
            prompt_id=request.prompt_id,
            base_story_id=request.base_story_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt or base story not found"
            )
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign prompt: {str(e)}"
        )

@router.get("/admin/base-stories/{story_id}", response_model=Dict[str, Any])
async def admin_get_base_story(story_id: str):
    """Get detailed information about a base story (admin only)"""
    # Authenticate admin
    
    try:
        with get_db() as db:
            base_story = db.query(BaseStory).filter(BaseStory.id == story_id).first()
            if not base_story:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Base story with ID {story_id} not found"
                )
            
            # Format the prompts
            prompts = []
            to_traverse = base_story.story_prompts.all()
            print(to_traverse)
            for prompt in to_traverse:
                prompts.append({
                    "id": prompt.id,
                    "name": prompt.name,
                    "system_prompt": prompt.system_prompt,
                    "turn_start": prompt.turn_start,
                    "turn_end": prompt.turn_end
                })
            
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
                "story_prompts": prompts
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve base story: {str(e)}"
        )

@router.delete("/admin/base-stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_base_story_endpoint(story_id: str): # Renamed, removed auth
    """Deletes a base story if no user stories depend on it (admin only)"""
    logger.info(f"Received request to delete base story ID: {story_id}")
    try:
        success, message = delete_base_story(story_id)

        if not success:
            # Determine appropriate status code based on message
            if "not found" in message:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
            elif "user stories depend on it" in message:
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
            else:
                 # General failure during delete
                 raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

        # Return 204 No Content on success
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise # Re-raise specific HTTP exceptions we raised
    except Exception as e:
        # Catch unexpected errors from the db_util function itself
        logger.exception(f"API Error: Unexpected error deleting base story {story_id}.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.put("/admin/base-stories/{story_id}", response_model=Dict[str, Any])
async def admin_update_base_story(story_id: str, request: BaseStoryRequest):
    """Updates an existing base story (admin only)"""
    # Authenticate admin
    
    try:
        # Get the base story
        # Update the story
        with get_db() as db:
            base_story = db.query(BaseStory).filter(BaseStory.id == story_id).first()
            base_story.title = request.title
            base_story.description = request.description
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
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update base story: {str(e)}"
        )

@router.delete("/admin/story-prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_story_prompt_endpoint(prompt_id: str): # Renamed, removed auth
    """Deletes a story prompt (admin only)"""
    logger.info(f"Received request to delete story prompt ID: {prompt_id}")
    try:
        success, message = delete_story_prompt(prompt_id)

        if not success:
            if "not found" in message:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
            else:
                # General failure
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

        # Return 204 No Content on success
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise # Re-raise specific HTTP exceptions
    except Exception as e:
        logger.exception(f"API Error: Unexpected error deleting story prompt {prompt_id}.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put("/admin/toggle-base-story/{story_id}", response_model=Dict[str, Any])
async def admin_toggle_base_story(story_id: str, active: bool):
    """Toggles a base story's active status (admin only)"""
    # Authenticate admin
    try:
        # Get the base story
        base_story = get_base_story(story_id)
        if not base_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Base story with ID {story_id} not found"
            )
        
        # Update the story
        with get_db() as db:
            base_story.is_active = active
            db.commit()
        
        return {
            "id": base_story.id,
            "is_active": base_story.is_active,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle base story status: {str(e)}"
        )