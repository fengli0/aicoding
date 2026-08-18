# Pydantic schemas for API request/response validation
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class StageStatusEnum(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class ShotSizeEnum(str, Enum):
    EXTREME_LONG = "extreme_long"
    LONG = "long"
    MEDIUM_LONG = "medium_long"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE = "close"
    EXTREME_CLOSE = "extreme_close"

class EditTransitionEnum(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    WIPE = "wipe"

class JobStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Project schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    status: StageStatusEnum
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Episode schemas
class EpisodeBase(BaseModel):
    episode_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    core_conflict: Optional[str] = None
    duration_target: Optional[int] = None

class EpisodeCreate(EpisodeBase):
    project_id: int

class EpisodeResponse(EpisodeBase):
    id: int
    status: StageStatusEnum
    
    class Config:
        from_attributes = True

# Entity schemas
class EntityProfileBase(BaseModel):
    name: str
    entity_type: str
    description: Optional[str] = None
    aliases: Optional[List[str]] = []
    relations: Optional[Dict[str, Any]] = {}
    world_building: Optional[Dict[str, Any]] = {}

class EntityProfileCreate(EntityProfileBase):
    project_id: int

class EntityProfileResponse(EntityProfileBase):
    id: int
    
    class Config:
        from_attributes = True

# Script Scene schemas
class ScriptSceneBase(BaseModel):
    scene_number: int
    location: str
    time_of_day: str
    characters: Optional[List[int]] = []
    costumes: Optional[str] = None
    props: Optional[List[Dict[str, Any]]] = []
    actions: Optional[str] = None
    dialogue: Optional[str] = None
    narration: Optional[str] = None
    audio_requirements: Optional[Dict[str, Any]] = {}

class ScriptSceneCreate(ScriptSceneBase):
    episode_id: int

class ScriptSceneResponse(ScriptSceneBase):
    id: int
    status: StageStatusEnum
    
    class Config:
        from_attributes = True

# Shot schemas
class ShotBase(BaseModel):
    shot_number: int
    shot_size: ShotSizeEnum = ShotSizeEnum.MEDIUM
    camera_position: Optional[str] = None
    camera_movement: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[str] = None
    estimated_duration: Optional[float] = None
    start_state: Optional[str] = None
    end_state: Optional[str] = None
    continuity_source: bool = True
    edit_transition: EditTransitionEnum = EditTransitionEnum.CUT

class ShotCreate(ShotBase):
    scene_id: int

class ShotResponse(ShotBase):
    id: int
    status: StageStatusEnum
    current_video_version_id: Optional[int] = None
    
    class Config:
        from_attributes = True

# Prompt Bundle schemas
class PromptBundleBase(BaseModel):
    positive_prompt: str
    negative_prompt: Optional[str] = ""
    model_params: Optional[Dict[str, Any]] = {}
    seed: Optional[int] = None

class PromptBundleCreate(PromptBundleBase):
    shot_id: Optional[int] = None
    entity_id: Optional[int] = None

class PromptBundleResponse(PromptBundleBase):
    id: int
    
    class Config:
        from_attributes = True

# Asset Version schemas
class AssetVersionBase(BaseModel):
    asset_type: str
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    dependencies: Optional[List[int]] = []
    error_message: Optional[str] = None
    is_selected: bool = False

class AssetVersionCreate(AssetVersionBase):
    shot_id: Optional[int] = None
    prompt_bundle_id: Optional[int] = None
    job_id: Optional[int] = None

class AssetVersionResponse(AssetVersionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Generation Job schemas
class GenerationJobBase(BaseModel):
    job_type: str
    priority: int = 0
    input_data: Dict[str, Any]
    max_retries: int = 2

class GenerationJobCreate(GenerationJobBase):
    pass

class GenerationJobResponse(GenerationJobBase):
    id: int
    status: JobStatusEnum
    comfyui_prompt_id: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

# Timeline Clip schemas
class TimelineClipBase(BaseModel):
    clip_type: str
    asset_version_id: int
    start_time: float
    duration: float
    track_index: int
    transition_type: Optional[str] = None
    transition_duration: Optional[float] = None

class TimelineClipCreate(TimelineClipBase):
    project_id: int
    episode_id: int

class TimelineClipResponse(TimelineClipBase):
    id: int
    
    class Config:
        from_attributes = True

# Export Job schemas
class ExportJobBase(BaseModel):
    export_type: str
    progress: float = 0.0
    error_message: Optional[str] = None

class ExportJobCreate(ExportJobBase):
    project_id: int
    episode_id: Optional[int] = None

class ExportJobResponse(ExportJobBase):
    id: int
    project_id: int
    episode_id: Optional[int] = None
    output_path: Optional[str] = None
    status: JobStatusEnum
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Novel import schemas
class NovelImportRequest(BaseModel):
    project_id: int
    content: Optional[str] = None
    file_path: Optional[str] = None
    file_type: str  # txt, md, docx, paste

class EpisodePlan(BaseModel):
    episode_number: int
    title: str
    summary: str
    core_conflict: str
    estimated_duration: int

class NovelImportResponse(BaseModel):
    entities: List[EntityProfileResponse]
    episodes: List[EpisodePlan]
    world_building: Dict[str, Any]
