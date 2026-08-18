# SQLAlchemy models for all core entities
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from ..db.database import Base

# Enums
class StageStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class ShotSize(str, enum.Enum):
    EXTREME_LONG = "extreme_long"
    LONG = "long"
    MEDIUM_LONG = "medium_long"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE = "close"
    EXTREME_CLOSE = "extreme_close"

class EditTransition(str, enum.Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    WIPE = "wipe"

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Core Models
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    status = Column(SQLEnum(StageStatus), default=StageStatus.DRAFT)
    
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")

class Episode(Base):
    __tablename__ = "episodes"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(255))
    summary = Column(Text)
    core_conflict = Column(Text)
    duration_target = Column(Integer)  # in seconds
    status = Column(SQLEnum(StageStatus), default=StageStatus.DRAFT)
    
    project = relationship("Project", back_populates="episodes")
    scenes = relationship("ScriptScene", back_populates="episode", cascade="all, delete-orphan")
    
class EntityProfile(Base):
    __tablename__ = "entity_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50))  # character, prop, location
    description = Column(Text)
    aliases = Column(JSON)  # list of alternative names
    relations = Column(JSON)  # relationships with other entities
    world_building = Column(JSON)  # world setting info
    
    variants = relationship("EntityVariant", back_populates="entity", cascade="all, delete-orphan")

class EntityVariant(Base):
    __tablename__ = "entity_variants"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(Integer, ForeignKey("entity_profiles.id"), nullable=False)
    variant_name = Column(String(255))  # e.g., "day", "night", "injured"
    description = Column(Text)
    prompt_bundle_id = Column(Integer, ForeignKey("prompt_bundles.id"))
    current_version_id = Column(Integer, ForeignKey("asset_versions.id"))
    
    entity = relationship("EntityProfile", back_populates="variants")
    current_version = relationship("AssetVersion", foreign_keys=[current_version_id])

class ScriptScene(Base):
    __tablename__ = "script_scenes"
    
    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    location = Column(String(255))
    time_of_day = Column(String(50))  # day, night, dawn, dusk
    characters = Column(JSON)  # list of character IDs
    costumes = Column(Text)
    props = Column(JSON)  # list of prop descriptions
    actions = Column(Text)
    dialogue = Column(Text)  # main dialogue
    narration = Column(Text)
    audio_requirements = Column(JSON)
    status = Column(SQLEnum(StageStatus), default=StageStatus.DRAFT)
    
    episode = relationship("Episode", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene", cascade="all, delete-orphan")

class Shot(Base):
    __tablename__ = "shots"
    
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("script_scenes.id"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    shot_size = Column(SQLEnum(ShotSize), default=ShotSize.MEDIUM)
    camera_position = Column(Text)
    camera_movement = Column(Text)
    action = Column(Text)
    dialogue = Column(Text)
    estimated_duration = Column(Float)  # seconds
    start_state = Column(Text)
    end_state = Column(Text)
    continuity_source = Column(Boolean, default=True)  # inherit from previous shot
    edit_transition = Column(SQLEnum(EditTransition), default=EditTransition.CUT)
    status = Column(SQLEnum(StageStatus), default=StageStatus.DRAFT)
    
    scene = relationship("ScriptScene", back_populates="shots")
    prompt_bundle = relationship("PromptBundle", uselist=False, back_populates="shot", cascade="all, delete-orphan")
    video_versions = relationship("AssetVersion", back_populates="shot", foreign_keys="AssetVersion.shot_id")
    current_video_version_id = Column(Integer, ForeignKey("asset_versions.id"))

class PromptBundle(Base):
    __tablename__ = "prompt_bundles"
    
    id = Column(Integer, primary_key=True, index=True)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=True)
    entity_id = Column(Integer, ForeignKey("entity_profiles.id"), nullable=True)
    
    positive_prompt = Column(Text)
    negative_prompt = Column(Text)
    model_params = Column(JSON)
    seed = Column(Integer)
    
    shot = relationship("Shot", back_populates="prompt_bundle")
    asset_versions = relationship("AssetVersion", back_populates="prompt_bundle", cascade="all, delete-orphan")

class AssetVersion(Base):
    __tablename__ = "asset_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_type = Column(String(50))  # image, video, audio
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=True)
    prompt_bundle_id = Column(Integer, ForeignKey("prompt_bundles.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("generation_jobs.id"))
    
    file_path = Column(String(1024))
    thumbnail_path = Column(String(1024))
    metadata = Column(JSON)  # model, workflow version, params, seed, inputs
    dependencies = Column(JSON)  # list of dependency version IDs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    error_message = Column(Text)
    is_selected = Column(Boolean, default=False)
    
    shot = relationship("Shot", back_populates="video_versions", foreign_keys=[shot_id])
    prompt_bundle = relationship("PromptBundle", back_populates="asset_versions")
    job = relationship("GenerationJob", back_populates="result_versions")

class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50))  # image, video, audio, llm
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    priority = Column(Integer, default=0)
    
    input_data = Column(JSON)  # prompts, references, params
    comfyui_prompt_id = Column(String(255))
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=2)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    
    result_versions = relationship("AssetVersion", back_populates="job")

class TimelineClip(Base):
    __tablename__ = "timeline_clips"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    
    clip_type = Column(String(50))  # video, audio_bgm, audio_sfx, audio_dialogue, subtitle
    asset_version_id = Column(Integer, ForeignKey("asset_versions.id"))
    start_time = Column(Float)  # seconds on timeline
    duration = Column(Float)
    track_index = Column(Integer)
    
    transition_type = Column(String(50))
    transition_duration = Column(Float)

class ExportJob(Base):
    __tablename__ = "export_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=True)
    
    export_type = Column(String(50))  # with_subtitles, no_subtitles, srt_only
    output_path = Column(String(1024))
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
