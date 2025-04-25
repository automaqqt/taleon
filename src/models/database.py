from typing import List, Optional
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# Association table for many-to-many relationship between StoryPrompt and BaseStory
story_prompt_association = Table(
    'story_prompt_association', 
    Base.metadata,
    Column('base_story_id', String, ForeignKey('base_stories.id')),
    Column('story_prompt_id', String, ForeignKey('story_prompts.id'))
)

class User(Base):
    """User model for authentication and story ownership"""
    __tablename__ = 'users'

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)  # Store hashed passwords only
    email = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    stories = relationship("UserStory", back_populates="user")

    def __repr__(self):
        return f"<User(username='{self.username}')>"

class BaseStory(Base):
    """Template stories that users can start from (e.g., 'Rotkäppchen')"""
    __tablename__ = 'base_stories'

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    original_tale_context = Column(Text, nullable=False)
    language = Column(String, default="Deutsch")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Initial prompts when starting the story
    initial_story_elements: Mapped[dict] = mapped_column(JSON, nullable=True)
    initial_system_prompt = Column(Text, nullable=False)
    initial_summary = Column(Text, nullable=False)
    
    # Relationships
    story_prompts = relationship("StoryPrompt", secondary=story_prompt_association, back_populates="base_stories", lazy="dynamic")
    user_stories = relationship("UserStory", back_populates="base_story")

    def __repr__(self):
        return f"<BaseStory(title='{self.title}')>"

class StoryPrompt(Base):
    """Prompts that are used at specific turns in the story"""
    __tablename__ = 'story_prompts'

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=False)
    turn_start = Column(Integer, nullable=False, default=0)  # Start using at this turn
    turn_end = Column(Integer, nullable=True)  # Stop using after this turn (null = no end)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    base_stories = relationship("BaseStory", secondary=story_prompt_association, back_populates="story_prompts")

    def __repr__(self):
        return f"<StoryPrompt(name='{self.name}', turn_range={self.turn_start}-{self.turn_end})>"

class UserStory(Base):
    """User-generated stories with progress and state"""
    __tablename__ = 'user_stories'

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    base_story_id = Column(String, ForeignKey('base_stories.id'), nullable=False)
    current_turn_number = Column(Integer, default=0)
    current_summary = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # JSON fields to store story details
    story_messages = Column(JSON, default=list)  # List of all messages in the story

    last_choices: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    
    # Fields from summary analysis
    main_character = Column(String, nullable=True)
    main_character_trait = Column(String, nullable=True)
    main_character_wish = Column(String, nullable=True)
    side_characters = Column(JSON, default=list)  # List of side characters with traits and wishes
    initial_task = Column(String, nullable=True)
    magic_elements = Column(JSON, default=list)  # List of magical elements
    obstacle = Column(String, nullable=True)
    reward = Column(String, nullable=True)
    cliffhanger_situation = Column(String, nullable=True)
    setting = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="stories")
    base_story = relationship("BaseStory", back_populates="user_stories")
    
    def __repr__(self):
        return f"<UserStory(title='{self.title}', turn={self.current_turn_number})>"

# Message model to store conversation history
class StoryMessage(Base):
    """Individual messages in a story conversation"""
    __tablename__ = 'story_messages'
    
    id = Column(String, primary_key=True, default=generate_uuid)
    story_id = Column(String, ForeignKey('user_stories.id'), nullable=False)
    turn_number = Column(Integer, nullable=False)
    message_type = Column(String, nullable=False)  # 'story', 'choice', 'userInput'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user_story = relationship("UserStory")
    
    def __repr__(self):
        return f"<StoryMessage(type='{self.message_type}', turn={self.turn_number})>"