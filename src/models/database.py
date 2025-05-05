# --- START OF FILE models/database.py ---

from typing import List, Optional, Dict, Any # Added Dict, Any
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Table
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import relationship, Mapped, mapped_column, declarative_base # Use declarative_base directly
from datetime import datetime
import uuid

# Use declarative_base() directly for modern SQLAlchemy
Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# --- Association Table (No changes needed in definition) ---
# Links StoryPrompt and StoryType (previously BaseStory)
story_prompt_association = Table(
    'story_prompt_association',
    Base.metadata,
    Column('story_type_id', String, ForeignKey('story_types.id'), primary_key=True), # Changed from base_story_id
    Column('story_prompt_id', String, ForeignKey('story_prompts.id'), primary_key=True)
)

# --- NEW: StoryType Model ---
class StoryType(Base):
    """Defines a type or genre of story (e.g., Fairy Tale, Sci-Fi)"""
    __tablename__ = 'story_types'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Prompts defining how to analyze/summarize stories of this type
    initial_extraction_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    dynamic_analysis_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    summary_prompt: Mapped[str] = mapped_column(Text, nullable=False) # Added

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    base_stories: Mapped[List["BaseStory"]] = relationship("BaseStory", back_populates="story_type")
    story_prompts: Mapped[List["StoryPrompt"]] = relationship(
        "StoryPrompt", secondary=story_prompt_association, back_populates="story_types"
    )

    def __repr__(self):
        return f"<StoryType(name='{self.name}')>"

# --- User Model (No changes needed) ---
class User(Base):
    """User model for authentication and story ownership"""
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="user")

    def __repr__(self):
        return f"<User(username='{self.username}')>"

# --- BaseStory Model (Modified) ---
class BaseStory(Base):
    """Template stories that users can start from, belonging to a StoryType"""
    __tablename__ = 'base_stories'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_tale_context: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, default="Deutsch")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Prompt for the very first turn (Turn 0)
    initial_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Initial summary used when starting a UserStory
    initial_summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Result of running StoryType.initial_extraction_prompt on original_tale_context
    initial_story_elements: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # Keep as dict

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign Key to StoryType
    story_type_id: Mapped[str] = mapped_column(String, ForeignKey('story_types.id'), nullable=False)

    # Relationships
    story_type: Mapped["StoryType"] = relationship("StoryType", back_populates="base_stories")
    user_stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="base_story")
    # Removed: story_prompts relationship

    def __repr__(self):
        return f"<BaseStory(title='{self.title}', type_id='{self.story_type_id}')>"

# --- StoryPrompt Model (Modified Relationship) ---
class StoryPrompt(Base):
    """Prompts used at specific turns, now associated with StoryType"""
    __tablename__ = 'story_prompts'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    turn_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (Changed to link to StoryType)
    story_types: Mapped[List["StoryType"]] = relationship(
        "StoryType", secondary=story_prompt_association, back_populates="story_prompts"
    )

    def __repr__(self):
        return f"<StoryPrompt(name='{self.name}', turn_range={self.turn_start}-{self.turn_end})>"

# --- UserStory Model (Modified) ---
class UserStory(Base):
    """User-generated stories with progress and evolving context"""
    __tablename__ = 'user_stories'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey('users.id'), nullable=False)
    base_story_id: Mapped[str] = mapped_column(String, ForeignKey('base_stories.id'), nullable=False)

    current_turn_number: Mapped[int] = mapped_column(Integer, default=0)
    current_summary: Mapped[str] = mapped_column(Text, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stores the evolving context extracted by StoryType.dynamic_analysis_prompt
    story_context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict) # Default to empty dict

    # History of messages (story segments, choices, user inputs)
    story_messages: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list) # Default to empty list
    # Last set of choices presented to the user
    last_choices: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="stories")
    base_story: Mapped["BaseStory"] = relationship("BaseStory", back_populates="user_stories")

    # Removed: Individual analysis fields (main_character, obstacle, etc.) - now in story_context

    def __repr__(self):
        return f"<UserStory(title='{self.title}', turn={self.current_turn_number})>"

# --- StoryMessage Model (No changes needed) ---
class StoryMessage(Base):
    """Individual messages in a story conversation"""
    __tablename__ = 'story_messages'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    story_id: Mapped[str] = mapped_column(String, ForeignKey('user_stories.id'), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    message_type: Mapped[str] = mapped_column(String, nullable=False) # 'story', 'choice', 'userInput'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user_story: Mapped["UserStory"] = relationship("UserStory") # Relationship setup for potential joins

    def __repr__(self):
        return f"<StoryMessage(type='{self.message_type}', turn={self.turn_number})>"

# --- END OF FILE models/database.py ---