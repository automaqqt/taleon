# --- START OF FILE database/db_utils.py ---

import os
from typing import Any, Dict, List, Optional, Tuple # Added Tuple
from sqlalchemy import create_engine, select, delete # Added select, delete
from sqlalchemy.orm import sessionmaker, scoped_session, joinedload, selectinload
from sqlalchemy.orm.attributes import flag_modified
# from sqlalchemy.ext.declarative import declarative_base # Base is imported from models now
from contextlib import contextmanager
from datetime import datetime
# Import all models
from ..models.database import (
    Base, User, BaseStory, StoryPrompt, UserStory, StoryMessage, StoryType,
    story_prompt_association # Import association table if needed directly
)
from passlib.hash import bcrypt
import logging

# Import SummaryService to perform initial analysis during BaseStory creation
from ..services.summary_service import SummaryService # Adjust path as needed

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Database
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./fairy_tales.db")

# Create engine and session factory
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith('sqlite') else {})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Instantiate services needed within db_utils
summary_service = SummaryService()

def init_db():
    """Initialize the database tables"""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    exist = authenticate_user('admin','storyteller123')
    if exist:
        logger.info("Database tables initialized.")
    else:
        create_user('admin','storyteller123','admin@test.com',True)

@contextmanager
def get_db():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.exception("Database session error occurred, rolling back.")
        db.rollback()
        raise e
    finally:
        # db.expunge_all() # Not always needed with scoped_session, can sometimes cause issues
        SessionLocal.remove() # Use remove() with scoped_session

# --- User management functions (No changes) ---
def create_user(username, password, email=None, is_admin=False):
    """Create a new user with hashed password"""
    with get_db() as db:
        hashed_password = bcrypt.hash(password)
        user = User(
            username=username,
            password_hash=hashed_password,
            email=email,
            is_admin=is_admin
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created user: {username}")
        return user

def authenticate_user(username, password):
    """Authenticate a user by username and password"""
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logger.warning(f"Authentication failed: User '{username}' not found.")
            return None
        if not bcrypt.verify(password, user.password_hash):
            logger.warning(f"Authentication failed: Incorrect password for user '{username}'.")
            return None
        logger.info(f"User '{username}' authenticated successfully.")
        # Update last login time
        user.last_login = datetime.utcnow()
        db.commit()
        return user

# --- StoryType CRUD functions ---
def create_story_type(name: str, initial_extraction_prompt: str, dynamic_analysis_prompt: str, summary_prompt: str, description: Optional[str] = None) -> StoryType:
    """Creates a new StoryType"""
    with get_db() as db:
        story_type = StoryType(
            name=name,
            description=description,
            initial_extraction_prompt=initial_extraction_prompt,
            dynamic_analysis_prompt=dynamic_analysis_prompt,
            summary_prompt=summary_prompt
        )
        db.add(story_type)
        db.commit()
        db.refresh(story_type)
        logger.info(f"Created StoryType: {name} (ID: {story_type.id})")
        return story_type

def get_story_type(story_type_id: str) -> Optional[StoryType]:
    """Gets a StoryType by ID"""
    with get_db() as db:
        stmt = select(StoryType).options(
            selectinload(StoryType.story_prompts)
        ).filter(StoryType.id == story_type_id)
        result = db.execute(stmt).scalar_one_or_none()
        if result:
            logger.debug(f"Fetched StoryType {story_type_id} with {len(result.story_prompts)} prompts eagerly loaded.")
        return result

def get_all_story_types() -> List[StoryType]:
    """Gets all StoryTypes"""
    with get_db() as db:
        return db.query(StoryType).order_by(StoryType.name).all()

def update_story_type(story_type_id: str, **updates: Any) -> Optional[StoryType]:
    """Updates a StoryType"""
    with get_db() as db:
        story_type = db.query(StoryType).filter(StoryType.id == story_type_id).first()
        if not story_type:
            logger.warning(f"Update failed: StoryType {story_type_id} not found.")
            return None

        updated = False
        for key, value in updates.items():
            if hasattr(story_type, key):
                setattr(story_type, key, value)
                updated = True
            else:
                logger.warning(f"Attempted to update non-existent attribute '{key}' on StoryType {story_type_id}")

        if updated:
            try:
                db.commit()
                db.refresh(story_type)
                logger.info(f"Updated StoryType: {story_type.name} (ID: {story_type_id})")
                return story_type
            except Exception as e:
                logger.exception(f"Error committing StoryType update for {story_type_id}")
                db.rollback()
                return None
        else:
            logger.info(f"No valid attributes provided for update on StoryType {story_type_id}")
            return story_type # Return existing object if no changes applied

def delete_story_type(story_type_id: str) -> Tuple[bool, str]:
    """Deletes a StoryType if no BaseStories depend on it"""
    with get_db() as db:
        # Check for dependent BaseStories
        base_story_count = db.query(BaseStory).filter(BaseStory.story_type_id == story_type_id).count()
        if base_story_count > 0:
            msg = f"Cannot delete StoryType {story_type_id}: {base_story_count} BaseStories depend on it."
            logger.warning(msg)
            return False, msg

        story_type = db.query(StoryType).filter(StoryType.id == story_type_id).first()
        if not story_type:
            msg = f"StoryType {story_type_id} not found for deletion."
            logger.warning(msg)
            return False, msg

        try:
            logger.info(f"Attempting to delete StoryType: {story_type.name} (ID: {story_type_id})")
            # Clear prompt associations
            story_type.story_prompts.clear()
            db.flush()

            db.delete(story_type)
            db.commit()
            msg = f"Successfully deleted StoryType {story_type_id}."
            logger.info(msg)
            return True, msg
        except Exception as e:
            msg = f"Error deleting StoryType {story_type_id}: {e}"
            logger.exception(msg)
            db.rollback()
            return False, msg

# --- Base Story functions (Modified create) ---
async def create_base_story( # Now async due to analysis call
    story_type_id: str,
    title: str,
    description: str,
    original_tale_context: str,
    initial_system_prompt: str,
    initial_summary: str,
    language: str = "Deutsch"
) -> Optional[BaseStory]:
    """Create a new base story template, performing initial analysis"""
    with get_db() as db:
        # 1. Get the StoryType
        story_type = db.query(StoryType).filter(StoryType.id == story_type_id).first()
        if not story_type:
            logger.error(f"Cannot create BaseStory: StoryType {story_type_id} not found.")
            return None

        # 2. Perform Initial Analysis (using the service, now async)
        logger.info(f"Performing initial analysis for new BaseStory '{title}' using StoryType '{story_type.name}' prompt.")
        try:
            # Use the specific initial extraction prompt from the StoryType
            analysis_result = await summary_service._analyze_initial_context(
                context_text=original_tale_context,
                # Pass the correct prompt from the story_type
                # Assuming _analyze_initial_context is modified or a new function exists
                # For now, let's assume it uses the INITIAL_ELEMENT_EXTRACTION_PROMPT internally if not passed
                # or we modify it:
                initial_prompt=story_type.initial_extraction_prompt 
            )
            if analysis_result:
                 logger.info(f"Initial analysis successful for '{title}'.")
                 initial_elements = analysis_result
            else:
                 logger.warning(f"Initial analysis did not return results for '{title}'. Proceeding without initial elements.")
                 initial_elements = None

        except Exception as e:
            logger.exception(f"Error during initial analysis for BaseStory '{title}': {e}. Proceeding without initial elements.")
            initial_elements = None

        # 3. Create the BaseStory object
        base_story = BaseStory(
            title=title,
            description=description,
            original_tale_context=original_tale_context,
            initial_system_prompt=initial_system_prompt,
            initial_summary=initial_summary,
            initial_story_elements=initial_elements, # Store analysis result
            language=language,
            story_type_id=story_type_id # Link to the StoryType
        )

        # 4. Add, commit, refresh
        db.add(base_story)
        db.commit()
        db.refresh(base_story) # Get the generated ID, etc.
        logger.info(f"Successfully created BaseStory '{title}' (ID: {base_story.id}) linked to StoryType {story_type_id}.")

        # Return a detached copy might be less necessary if session management is good
        # Just return the committed object
        return base_story

def get_base_story(story_id: str) -> Optional[BaseStory]:
    """Get a base story by ID"""
    with get_db() as db:
        stmt = select(BaseStory).options(
            joinedload(BaseStory.story_type)
        ).filter(BaseStory.id == story_id)
        result = db.execute(stmt).scalar_one_or_none()
        if result:
            logger.debug(f"Fetched BaseStory {story_id} with StoryType '{result.story_type.name if result.story_type else 'None'}' eagerly loaded.")
        return result
def get_all_base_stories(active_only=True) -> List[BaseStory]:
    """Get all base stories, eagerly loading story types."""
    with get_db() as db:
        query = db.query(BaseStory).options(joinedload(BaseStory.story_type)) # Eager load type
        if active_only:
            query = query.filter(BaseStory.is_active == True)
        return query.order_by(BaseStory.title).all()

def delete_base_story(story_id: str) -> tuple[bool, str]:
    """Deletes a base story if no user stories depend on it"""
    # Logic remains the same, checks UserStory dependencies
    with get_db() as db:
        user_story_count = db.query(UserStory).filter(UserStory.base_story_id == story_id).count()
        if user_story_count > 0:
            msg = f"Cannot delete BaseStory {story_id}: {user_story_count} user stories depend on it."
            logger.warning(msg)
            return False, msg

        base_story = db.query(BaseStory).filter(BaseStory.id == story_id).first()
        if not base_story:
            msg = f"BaseStory with ID {story_id} not found for deletion."
            logger.warning(msg)
            return False, msg

        try:
            logger.info(f"Attempting to delete BaseStory: {base_story.title} (ID: {story_id})")
            db.delete(base_story)
            db.commit()
            msg = f"Successfully deleted BaseStory {story_id}."
            logger.info(msg)
            return True, msg
        except Exception as e:
            msg = f"Error deleting BaseStory {story_id}: {e}"
            logger.exception(msg)
            db.rollback()
            return False, msg

# --- Story Prompt functions (Modified association, get) ---
def create_story_prompt(name, system_prompt, turn_start=0, turn_end=None) -> StoryPrompt:
    """Create a new story prompt (not associated yet)"""
    with get_db() as db:
        prompt = StoryPrompt(
            name=name,
            system_prompt=system_prompt,
            turn_start=turn_start,
            turn_end=turn_end
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        logger.info(f"Created StoryPrompt: {name} (ID: {prompt.id})")
        return prompt

def assign_prompt_to_story_type(prompt_id: str, story_type_id: str) -> bool:
    """Associate a prompt with a StoryType"""
    with get_db() as db:
        prompt = db.query(StoryPrompt).filter(StoryPrompt.id == prompt_id).first()
        if not prompt:
            logger.warning(f"Assign prompt failed: Prompt {prompt_id} not found.")
            return False

        story_type = db.query(StoryType).filter(StoryType.id == story_type_id).first()
        if not story_type:
            logger.warning(f"Assign prompt failed: StoryType {story_type_id} not found.")
            return False

        if prompt not in story_type.story_prompts:
            story_type.story_prompts.append(prompt)
            try:
                db.commit()
                logger.info(f"Assigned Prompt {prompt_id} to StoryType {story_type_id}.")
                return True
            except Exception as e:
                 logger.exception(f"Failed to commit prompt assignment {prompt_id} -> {story_type_id}.")
                 db.rollback()
                 return False
        else:
            logger.info(f"Prompt {prompt_id} already assigned to StoryType {story_type_id}.")
            return True

def get_story_prompts_for_turn(story_type_id: str, turn_number: int) -> List[StoryPrompt]:
    """Get appropriate story prompts for a given turn from a StoryType"""
    # The previous query using joins was correct for filtering based on StoryType.
    # No eager loading needed here as we return the prompt objects themselves.
    with get_db() as db:
        prompts = db.query(StoryPrompt)\
            .join(story_prompt_association, StoryPrompt.id == story_prompt_association.c.story_prompt_id)\
            .join(StoryType, StoryType.id == story_prompt_association.c.story_type_id)\
            .filter(
                StoryType.id == story_type_id,
                StoryPrompt.turn_start <= turn_number,
                (StoryPrompt.turn_end == None) | (StoryPrompt.turn_end >= turn_number)
            )\
            .order_by(StoryPrompt.turn_start.desc(), StoryPrompt.id)\
            .all()
        if prompts: logger.debug(f"Found {len(prompts)} prompts for StoryType {story_type_id}, Turn {turn_number}. Top priority: '{prompts[0].name}'")
        else: logger.debug(f"No specific prompt found for StoryType {story_type_id}, Turn {turn_number}.")
        return prompts

def delete_story_prompt(prompt_id: str) -> tuple[bool, str]:
    """Deletes a story prompt and its associations"""
    with get_db() as db:
        prompt = db.query(StoryPrompt).filter(StoryPrompt.id == prompt_id).first()
        if not prompt:
            msg = f"StoryPrompt with ID {prompt_id} not found for deletion."
            logger.warning(msg)
            return False, msg

        try:
            logger.info(f"Attempting to delete StoryPrompt: {prompt.name} (ID: {prompt_id})")
            # Clear associations (SQLAlchemy handles this via relationship cascade='all, delete-orphan' or similar,
            # but explicit clear is safe if cascade isn't set up perfectly)
            if hasattr(prompt, 'story_types'):
                 prompt.story_types.clear() # Clear the collection on the prompt side
                 db.flush() # Process the removal of associations

            db.delete(prompt)
            db.commit()
            msg = f"Successfully deleted StoryPrompt {prompt_id}."
            logger.info(msg)
            return True, msg
        except Exception as e:
            msg = f"Error deleting StoryPrompt {prompt_id}: {e}"
            logger.exception(msg)
            db.rollback()
            return False, msg

# --- User Story functions (Modified create) ---
def create_user_story(user_id, base_story_id, title=None) -> Optional[UserStory]:
    """Create a new story for a user based on a template"""
    with get_db() as db:
        base_story = db.query(BaseStory).filter(BaseStory.id == base_story_id).first()
        if not base_story:
            logger.error(f"Cannot create UserStory: BaseStory {base_story_id} not found.")
            return None

        # Default title if none provided
        story_title = title or f"{base_story.title}'s Adventure"

        # Initialize story_context (start empty or copy some initial elements)
        initial_context = {}
        if base_story.initial_story_elements:
            # Example: copy only specific keys if needed
            # for key in ["main_character", "setting", "language"]:
            #    if key in base_story.initial_story_elements:
            #        initial_context[key] = base_story.initial_story_elements[key]
            # Or just copy the whole thing if appropriate for starting context:
             initial_context = base_story.initial_story_elements.copy() # Make a copy
             logger.debug(f"Initializing UserStory context with elements from BaseStory {base_story_id}")


        user_story = UserStory(
            title=story_title,
            user_id=user_id,
            base_story_id=base_story_id,
            current_summary=base_story.initial_summary, # Use initial summary from BaseStory
            current_turn_number=0,
            story_context=initial_context, # Use initialized context
            story_messages=[], # Start with empty messages
            last_choices=None # Start with no choices
        )
        # Removed setting of individual analysis fields

        db.add(user_story)
        db.commit()
        db.refresh(user_story)
        logger.info(f"Created UserStory '{story_title}' (ID: {user_story.id}) for user {user_id} based on BaseStory {base_story_id}.")
        return user_story

def get_user_story(story_id: str) -> Optional[UserStory]:
    """Get a user story by ID, eagerly loading base_story and its story_type."""
    with get_db() as db:
        # Use joinedload to load the chain UserStory -> BaseStory -> StoryType
        stmt = select(UserStory).options(
            joinedload(UserStory.base_story).joinedload(BaseStory.story_type)
        ).filter(UserStory.id == story_id)
        result = db.execute(stmt).scalar_one_or_none()
        if result:
             logger.debug(f"Fetched UserStory {story_id} with BaseStory and StoryType eagerly loaded.")
        return result


def get_user_stories(user_id, completed=None) -> List[UserStory]:
    """Get all stories for a user, eagerly loading base story titles."""
    # Use joinedload for BaseStory to get the title efficiently
    with get_db() as db:
        query = db.query(UserStory).options(joinedload(UserStory.base_story)).filter(UserStory.user_id == user_id)
        if completed is not None:
            query = query.filter(UserStory.is_completed == completed)
        return query.order_by(UserStory.updated_at.desc()).all()

def update_user_story(story_id: str, **updates: Any) -> Optional[UserStory]:
    """Update a user story with new values (can include story_context)"""
    with get_db() as db:
        story = db.query(UserStory).filter(UserStory.id == story_id).first()
        if not story:
            logger.warning(f"Update failed: UserStory {story_id} not found.")
            return None

        logger.debug(f"Attempting to update UserStory {story_id} with: {updates.keys()}")
        updated_any = False
        for key, value in updates.items():
            if hasattr(story, key):
                # Special handling for JSON field 'story_context'
                if key == 'story_context':
                    if isinstance(value, dict):
                        # Replace the whole dict or merge? Let's replace for simplicity via setattr.
                        # For merging, you'd fetch story.story_context and update it.
                        setattr(story, key, value)
                        flag_modified(story, key) # Crucial for JSON updates
                        logger.debug(f"Updated UserStory {story_id} field '{key}' (JSON - flagged modified).")
                        updated_any = True
                    else:
                        logger.warning(f"Skipping update for '{key}' on UserStory {story_id}: value is not a dict ({type(value)}).")
                # Special handling for JSON field 'story_messages' (less common via update_user_story)
                elif key == 'story_messages':
                     if isinstance(value, list):
                        setattr(story, key, value)
                        flag_modified(story, key)
                        logger.debug(f"Updated UserStory {story_id} field '{key}' (JSON - flagged modified).")
                        updated_any = True
                     else:
                        logger.warning(f"Skipping update for '{key}' on UserStory {story_id}: value is not a list ({type(value)}).")
                # Handle regular attributes
                else:
                    setattr(story, key, value)
                    logger.debug(f"Updated UserStory {story_id} field '{key}' to '{value}'.")
                    updated_any = True
            else:
                logger.warning(f"Attribute '{key}' not found on UserStory object {story_id}.")

        if not updated_any:
            logger.info(f"No attributes were updated for UserStory {story_id}.")
            return story # Return existing object

        try:
            db.commit()
            logger.info(f"Commit successful for UserStory {story_id} update.")
        except Exception as e:
            logger.exception(f"COMMIT FAILED for UserStory {story_id} update: {e}")
            db.rollback()
            return None # Indicate failure

        db.refresh(story)
        logger.debug(f"UserStory {story_id} refreshed.")
        return story

def add_story_message(story_id: str, message_type: str, content: str, turn_number: int) -> Optional[StoryMessage]:
    """Add a message to a story's conversation history and update JSON field"""
    logger.debug(f"Attempting to add message to story {story_id}: Type='{message_type}', Turn={turn_number}, Content='{content[:50]}...'")
    with get_db() as db:
        try:
            # 1. Get the story first to ensure it exists
            story = db.query(UserStory).filter(UserStory.id == story_id).first()
            if not story:
                logger.error(f"Cannot add message: UserStory {story_id} not found.")
                return None

            # 2. Create the StoryMessage record (optional if only using JSON field)
            # If you rely *solely* on the JSON field, you might skip creating separate StoryMessage rows.
            # However, having rows allows easier querying/indexing of individual messages.
            # message = StoryMessage(
            #     story_id=story_id,
            #     message_type=message_type,
            #     content=content,
            #     turn_number=turn_number
            # )
            # db.add(message)
            # logger.debug(f"StoryMessage object created for story {story_id}.")

            # 3. Update the story's messages JSON field
            logger.debug(f"Found UserStory {story_id} to update JSON field.")
            if not isinstance(story.story_messages, list):
                logger.warning(f"UserStory {story_id} story_messages field was not a list ({type(story.story_messages)}). Initializing.")
                story.story_messages = []

            story.story_messages.append({
                "type": message_type,
                "content": content,
                "turn": turn_number,
                "timestamp": datetime.utcnow().isoformat() # Add timestamp to JSON entry
            })
            logger.debug(f"Appended message to story_messages list for story {story_id}. List size now: {len(story.story_messages)}")

            # Mark the JSON field as modified
            flag_modified(story, "story_messages")
            logger.debug(f"Flagged 'story_messages' as modified for story {story_id}.")

            # 4. Commit changes
            db.commit()
            logger.info(f"Successfully committed message for story {story_id} (Turn {turn_number}).")
            # db.refresh(message) # Refresh if you created the separate message object and need its ID
            # return message
            return True # Indicate success (or return the updated story object if needed)

        except Exception as e:
            logger.exception(f"Error adding story message for story {story_id}: {e}")
            db.rollback()
            return None # Indicate failure

def get_story_messages(story_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get messages for a story directly from the JSON field"""
    with get_db() as db:
        story = db.query(UserStory).filter(UserStory.id == story_id).first()
        if not story or not isinstance(story.story_messages, list):
            return []

        messages = story.story_messages
        # Sort by timestamp within the JSON if available and needed, otherwise assume order is okay
        # messages.sort(key=lambda x: x.get('timestamp', '')) # Example sort

        if limit:
            return messages[-limit:] # Return the last 'limit' messages
        else:
            return messages

# --- Summary Data Update Function (Revised Role) ---
def update_story_summary_data(story_id: str, summary_data: Dict[str, Any]) -> Optional[UserStory]:
    """Update specific fields, primarily 'current_summary', in a user story."""
    # This function is now less critical for context fields which are in story_context.
    # Keep it mainly for updating the summary text itself.
    with get_db() as db:
        story = db.query(UserStory).filter(UserStory.id == story_id).first()
        if not story:
            logger.warning(f"Update summary data failed: UserStory {story_id} not found.")
            return None

        updated = False
        if 'current_summary' in summary_data and summary_data['current_summary'] is not None:
            if story.current_summary != summary_data['current_summary']:
                 setattr(story, 'current_summary', summary_data['current_summary'])
                 logger.debug(f"Updating current_summary for UserStory {story_id}.")
                 updated = True
            else:
                 logger.debug(f"current_summary for UserStory {story_id} is unchanged.")

        # Optionally handle other specific fields if needed, but prefer updating story_context via update_user_story
        # Example:
        # if 'some_other_direct_field' in summary_data and summary_data['some_other_direct_field'] is not None:
        #     setattr(story, 'some_other_direct_field', summary_data['some_other_direct_field'])
        #     updated = True

        if updated:
            try:
                db.commit()
                db.refresh(story)
                logger.info(f"Successfully updated summary data for UserStory {story_id}.")
                return story
            except Exception as e:
                logger.exception(f"Error committing summary data update for UserStory {story_id}.")
                db.rollback()
                return None
        else:
            logger.info(f"No summary data changes to commit for UserStory {story_id}.")
            return story

def db_get_all_story_prompts() -> List[StoryPrompt]:
    """Gets all StoryPrompts"""
    with get_db() as db:
        return db.query(StoryPrompt).order_by(StoryPrompt.name).all()

def remove_prompt_from_story_type(prompt_id: str, story_type_id: str) -> bool:
    """Remove association between a prompt and a StoryType"""
    with get_db() as db:
        try:
            story_type = db.query(StoryType).options(joinedload(StoryType.story_prompts)).filter(StoryType.id == story_type_id).first()
            if not story_type:
                logger.warning(f"Remove prompt failed: StoryType {story_type_id} not found.")
                return False

            prompt_to_remove = None
            for prompt in story_type.story_prompts:
                if prompt.id == prompt_id:
                    prompt_to_remove = prompt
                    break

            if prompt_to_remove:
                story_type.story_prompts.remove(prompt_to_remove)
                db.commit()
                logger.info(f"Removed Prompt {prompt_id} assignment from StoryType {story_type_id}.")
                return True
            else:
                logger.warning(f"Remove prompt failed: Prompt {prompt_id} was not assigned to StoryType {story_type_id}.")
                return False
        except Exception as e:
            logger.exception(f"Error removing prompt assignment {prompt_id} from {story_type_id}.")
            db.rollback()
            return False

def get_story_prompt(prompt_id: str) -> Optional[StoryPrompt]:
    """Gets a single StoryPrompt by its ID."""
    with get_db() as db:
        # No relationships typically needed just for editing the prompt itself
        return db.query(StoryPrompt).filter(StoryPrompt.id == prompt_id).first()

def update_story_prompt(prompt_id: str, **updates: Any) -> Optional[StoryPrompt]:
    """Updates attributes of an existing StoryPrompt."""
    with get_db() as db:
        prompt = db.query(StoryPrompt).filter(StoryPrompt.id == prompt_id).first()
        if not prompt:
            logger.warning(f"Update failed: StoryPrompt {prompt_id} not found.")
            return None

        updated = False
        allowed_updates = ['name', 'system_prompt', 'turn_start', 'turn_end'] # Define updatable fields
        for key, value in updates.items():
            if key in allowed_updates:
                # Basic type validation could be added here if needed
                setattr(prompt, key, value)
                updated = True
            else:
                logger.warning(f"Attempted to update non-allowed attribute '{key}' on StoryPrompt {prompt_id}")

        if updated:
            try:
                db.commit()
                db.refresh(prompt)
                logger.info(f"Updated StoryPrompt: {prompt.name} (ID: {prompt_id})")
                return prompt
            except Exception as e:
                logger.exception(f"Error committing StoryPrompt update for {prompt_id}")
                db.rollback()
                return None
        else:
            logger.info(f"No valid attributes provided for update on StoryPrompt {prompt_id}")
            return prompt # Return existing object if no changes applied

# --- END OF FILE database/db_utils.py ---