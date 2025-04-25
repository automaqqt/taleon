import os
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from ..models.database import Base, User, BaseStory, StoryPrompt, UserStory, StoryMessage
from passlib.hash import bcrypt
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Configure Database
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./fairy_tales.db")

# Create engine and session factory
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith('sqlite') else {})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def init_db():
    """Initialize the database tables"""
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.expunge_all()  # Detach all objects from session but keep their state
        db.close()

# User management functions
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
        return user

def authenticate_user(username, password):
    """Authenticate a user by username and password"""
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not bcrypt.verify(password, user.password_hash):
            return None
        return user

# Base Story functions
def create_base_story(title, description, original_tale_context, initial_system_prompt, initial_summary, language="Deutsch", initial_story_elements: Optional[Dict[str, Any]] = None):
    """Create a new base story template"""
    with get_db() as db:
        print('hello')
        base_story = BaseStory(
            title=title,
            description=description,
            original_tale_context=original_tale_context,
            initial_system_prompt=initial_system_prompt,
            initial_summary=initial_summary,
            initial_story_elements=initial_story_elements,
            language=language
        )
        print(base_story)
        db.add(base_story)
        db.commit()
        
        # Create a detached copy with all the attributes
        # Or if you have an id, you might just return that
        detached_story = BaseStory(
            id=base_story.id,
            title=base_story.title,
            description=base_story.description,
            original_tale_context=base_story.original_tale_context,
            initial_system_prompt=base_story.initial_system_prompt,
            initial_summary=base_story.initial_summary,
            language=base_story.language,
            initial_story_elements=base_story.initial_story_elements
        )
        print("success")
        return detached_story

def get_base_story(story_id):
    """Get a base story by ID"""
    with get_db() as db:
        return db.query(BaseStory).filter(BaseStory.id == story_id).first()

def get_all_base_stories(active_only=True):
    """Get all base stories, optionally filtering by active status"""
    with get_db() as db:
        query = db.query(BaseStory)
        if active_only:
            query = query.filter(BaseStory.is_active == True)
        return query.all()

def delete_base_story(story_id: str) -> tuple[bool, str]:
    """
    Deletes a base story by ID.
    Prevents deletion if any UserStory references it.
    Returns: (success: bool, message: str)
    """
    with get_db() as db:
        # 1. Check for referencing UserStories
        user_story_count = db.query(UserStory).filter(UserStory.base_story_id == story_id).count()
        if user_story_count > 0:
            msg = f"Cannot delete BaseStory {story_id}: {user_story_count} user stories depend on it."
            logger.warning(msg)
            return False, msg

        # 2. Find the BaseStory
        base_story = db.query(BaseStory).filter(BaseStory.id == story_id).first()
        if not base_story:
            msg = f"BaseStory with ID {story_id} not found for deletion."
            logger.warning(msg)
            return False, msg

        try:
            logger.info(f"Attempting to delete BaseStory: {base_story.title} (ID: {story_id})")
            # 3. Clear prompt associations (SQLAlchemy might handle this via cascade on the assoc table, but explicit is safer)
            # If using association_proxy or direct relationship, this clears the link
            #base_story.story_prompts.clear() # Assuming 'story_prompts' is the relationship name
            db.flush() # Ensure association changes are processed before delete

            # 4. Delete the BaseStory
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

# Story Prompt functions
def create_story_prompt(name, system_prompt, turn_start=0, turn_end=None):
    """Create a new story prompt"""
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
        return prompt

def assign_prompt_to_base_story(prompt_id: str, base_story_id: str) -> bool:
    """Associate a prompt with a base story"""
    with get_db() as db:
        prompt = db.query(StoryPrompt).filter(StoryPrompt.id == prompt_id).first()
        if not prompt:
            logger.warning(f"Assign prompt failed: Prompt {prompt_id} not found.")
            return False

        base_story = db.query(BaseStory).filter(BaseStory.id == base_story_id).first()
        if not base_story:
            logger.warning(f"Assign prompt failed: BaseStory {base_story_id} not found.")
            return False

        # Avoid duplicates if necessary (depends on relationship configuration)
        if prompt not in base_story.story_prompts:
            base_story.story_prompts.append(prompt)
            try:
                db.commit()
                logger.info(f"Assigned Prompt {prompt_id} to BaseStory {base_story_id}.")
                return True
            except Exception as e:
                 logger.exception(f"Failed to commit prompt assignment {prompt_id} -> {base_story_id}.")
                 db.rollback()
                 return False
        else:
            logger.info(f"Prompt {prompt_id} already assigned to BaseStory {base_story_id}.")
            return True # Considered success if already assigned

def get_story_prompts_for_turn(base_story_id: str, turn_number: int) -> List[StoryPrompt]:
    """Get appropriate story prompts for a given turn in a base story"""
    # This logic might be better placed within get_base_story or called separately
    # to avoid redundant BaseStory lookups if called sequentially.
    with get_db() as db:
        # Efficiently fetch prompts for the base story matching the turn criteria
        prompts = db.query(StoryPrompt).join(BaseStory.story_prompts).filter(
            BaseStory.id == base_story_id,
            StoryPrompt.turn_start <= turn_number,
            (StoryPrompt.turn_end == None) | (StoryPrompt.turn_end >= turn_number) # Handles NULL turn_end
        ).order_by(StoryPrompt.turn_start.desc(), StoryPrompt.id).all() # Prioritize higher turn_start
        return prompts

def delete_story_prompt(prompt_id: str) -> tuple[bool, str]:
    """
    Deletes a story prompt by ID.
    Removes associations from BaseStories.
    Returns: (success: bool, message: str)
    """
    with get_db() as db:
        prompt = db.query(StoryPrompt).filter(StoryPrompt.id == prompt_id).first()
        if not prompt:
            msg = f"StoryPrompt with ID {prompt_id} not found for deletion."
            logger.warning(msg)
            return False, msg

        try:
            logger.info(f"Attempting to delete StoryPrompt: {prompt.name} (ID: {prompt_id})")
            # 1. Remove associations (SQLAlchemy might handle this, but explicit is safer)
            # If 'base_stories' is the back-reference from Prompt to BaseStory:
            if hasattr(prompt, 'base_stories'):
                 prompt.base_stories.clear() # Clear the collection on the prompt side
                 db.flush() # Process the removal of associations

            # 2. Delete the prompt
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

# User Story functions
def create_user_story(user_id, base_story_id, title=None):
    """Create a new story for a user based on a template"""
    with get_db() as db:
        base_story = db.query(BaseStory).filter(BaseStory.id == base_story_id).first()
        if not base_story:
            return None
        
        # Default title if none provided
        if not title:
            title = f"{base_story.title}'s Adventure"
        print(base_story.initial_story_elements)
        initial_elements = base_story.initial_story_elements or {}

        user_story = UserStory(
            title=title,
            user_id=user_id,
            base_story_id=base_story_id,
            current_summary=base_story.initial_summary,
            current_turn_number=0,
            main_character=initial_elements.get("main_character"),
            main_character_trait=initial_elements.get("main_character_trait"),
            main_character_wish=initial_elements.get("main_character_wish"),
            side_characters=initial_elements.get("side_character", []), 
            setting=initial_elements.get("setting"),
            initial_task=initial_elements.get("initial_task"),
            magic_elements=initial_elements.get("magic_elements", []), 
            story_messages=[]
        )
        db.add(user_story)
        db.commit()
        db.refresh(user_story)
        return user_story

def get_user_story(story_id):
    """Get a user story by ID"""
    with get_db() as db:
        return db.query(UserStory).filter(UserStory.id == story_id).first()

def get_user_stories(user_id, completed=None):
    """Get all stories for a user, optionally filtering by completion status"""
    with get_db() as db:
        query = db.query(UserStory).filter(UserStory.user_id == user_id)
        if completed is not None:
            query = query.filter(UserStory.is_completed == completed)
        return query.order_by(UserStory.updated_at.desc()).all()

def update_user_story(story_id, **updates):
    """Update a user story with new values"""
    with get_db() as db:
        story = db.query(UserStory).filter(UserStory.id == story_id).first()
        if not story:
            print(f"Update failed: Story {story_id} not found.") # Use logger preferably
            return None

        print(f"Attempting to update story {story_id} with: {updates}") # Log input
        updated_any = False
        for key, value in updates.items():
            has_the_attr = hasattr(story, key) # Check hasattr result
            print(f"Checking key '{key}'. hasattr: {has_the_attr}")
            if has_the_attr:
                print(f"Setting attribute '{key}' to '{value}'")
                setattr(story, key, value)
                updated_any = True
            else:
                print(f"Attribute '{key}' not found on story object.")

        if not updated_any:
            print("No attributes were updated.")
            # Potentially return early or just proceed to commit (which will do nothing)

        try:
            db.commit()
            print(f"Commit successful for story {story_id}.")
        except Exception as e:
            print(f"COMMIT FAILED for story {story_id}: {e}") # Log commit errors
            db.rollback()
            raise # Re-raise after logging

        db.refresh(story)
        print(f"Story {story_id} refreshed. Current turn now: {story.current_turn_number}")
        return story

def add_story_message(story_id, message_type, content, turn_number):
    """Add a message to a story's conversation history"""
    logger.debug(f"Attempting to add message to story {story_id}: Type='{message_type}', Turn={turn_number}, Content='{content[:50]}...'") # Log entry
    with get_db() as db:
        try:
            # 1. Create the new StoryMessage record
            message = StoryMessage(
                story_id=story_id,
                message_type=message_type,
                content=content,
                turn_number=turn_number
            )
            db.add(message)
            logger.debug(f"StoryMessage object created and added to session for story {story_id}.")

            # 2. Update the story's messages JSON field
            story = db.query(UserStory).filter(UserStory.id == story_id).first()
            if story:
                logger.debug(f"Found UserStory {story_id} to update JSON field.")
                # Ensure the JSON field is initialized as a list if it's None or empty
                if not isinstance(story.story_messages, list):
                    logger.warning(f"UserStory {story_id} story_messages field was not a list ({type(story.story_messages)}). Initializing.")
                    story.story_messages = [] # Initialize/reset to empty list

                # Append the new message dictionary
                story.story_messages.append({
                    "type": message_type,
                    "content": content,
                    "turn": turn_number
                })
                logger.debug(f"Appended message to story_messages list for story {story_id}. List size now: {len(story.story_messages)}")

                # !!! THIS IS THE FIX !!!
                # Explicitly mark the 'story_messages' field as modified
                flag_modified(story, "story_messages")
                logger.debug(f"Flagged 'story_messages' as modified for story {story_id}.")

            else:
                logger.warning(f"Could not find UserStory with ID {story_id} to update JSON field. StoryMessage record will still be added.")

            # 3. Commit changes
            db.commit()
            logger.info(f"Successfully committed message for story {story_id} (Turn {turn_number}).")
            # The 'message' object might not have its ID populated until after commit depending on DB/config
            # If you need the committed message ID, you might need db.refresh(message) after commit
            return message

        except Exception as e:
            logger.exception(f"Error adding story message for story {story_id}: {e}")
            db.rollback() # Rollback on any error during the process
            # Optionally re-raise the exception if the caller needs to know
            # raise
            return None # Or return None to indicate failure

def get_story_messages(story_id, limit=None):
    """Get messages for a story, optionally limiting the number returned"""
    with get_db() as db:
        query = db.query(StoryMessage).filter(StoryMessage.story_id == story_id)
        query = query.order_by(StoryMessage.timestamp.asc())
        
        if limit:
            query = query.limit(limit)
            
        return query.all()

# Create or update functions for summary data
def update_story_summary_data(story_id, summary_data):
    """Update a story with new summary data"""
    with get_db() as db:
        story = db.query(UserStory).filter(UserStory.id == story_id).first()
        if not story:
            return None
        
        # Update fields if they exist in summary_data
        for field in [
            'main_character', 'main_character_trait', 'main_character_wish',
            'side_characters', 'initial_task', 'magic_elements',
            'obstacle', 'reward', 'cliffhanger_situation', 'setting',
            'current_summary'
        ]:
            if field in summary_data and summary_data[field] is not None:
                # Don't overwrite with None values
                setattr(story, field, summary_data[field])
        
        db.commit()
        db.refresh(story)
        return story