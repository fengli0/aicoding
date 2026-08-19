# Pydantic schemas for API request/response
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

# Use string literals instead of enum classes for Pydantic compatibility
StageStatus = str
JobStatus = str
EditTransition = str
ShotSize = str


# Request Schemas
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class NovelImportRequest(BaseModel):
    text: Optional[str] = None
    file_path: Optional[str] = None
    target_episodes: Optional[int] = 10

class EpisodeCreate(BaseModel):
    project_id: int
    episode_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    core_conflict: Optional[str] = None

class ScriptSceneCreate(BaseModel):
    episode_id: int
    scene_number: int
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    actions: Optional[str] = None

class ShotCreate(BaseModel):
    scene_id: int
    shot_number: int
    shot_size: Optional[str] = "medium"
    camera_movement: Optional[str] = None
    action: Optional[str] = None
    estimated_duration: Optional[float] = None
    continuity_source: Optional[str] = "reference_image"
    edit_transition: Optional[str] = "cut"

class PromptBundleCreate(BaseModel):
    shot_id: Optional[int] = None
    positive_prompt: str
    negative_prompt: Optional[str] = ""
    model_params: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None

class AssetVersionCreate(BaseModel):
    asset_type: str  # image, video, audio
    shot_id: Optional[int] = None
    prompt_bundle_id: Optional[int] = None
    job_id: Optional[int] = None
    file_path: str
    metadata: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[int]] = None

class GenerationJobCreate(BaseModel):
    job_type: str  # image, video, audio, llm
    input_data: Dict[str, Any]
    priority: Optional[int] = 0
    max_retries: Optional[int] = 2

class EntityProfileCreate(BaseModel):
    project_id: int
    name: str
    entity_type: Optional[str] = "character"
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    relations: Optional[Dict[str, Any]] = None

class EntityProfileResponse(BaseModel):
    id: int
    project_id: int
    name: str
    entity_type: str
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    relations: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class NovelImportResponse(BaseModel):
    entities: List[EntityProfileResponse]
    episodes: List[Dict[str, Any]]
    world_building: Optional[Dict[str, Any]] = None


# Response Schemas
class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str = "draft"
    created_at: datetime
    
    class Config:
        from_attributes = True

class EpisodeResponse(BaseModel):
    id: int
    project_id: int
    episode_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    core_conflict: Optional[str] = None
    status: str = "draft"
    
    class Config:
        from_attributes = True

class ScriptSceneResponse(BaseModel):
    id: int
    episode_id: int
    scene_number: int
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    actions: Optional[str] = None
    status: str = "draft"
    
    class Config:
        from_attributes = True

class ShotResponse(BaseModel):
    id: int
    scene_id: int
    shot_number: int
    shot_size: str = "medium"
    camera_movement: Optional[str] = None
    action: Optional[str] = None
    estimated_duration: Optional[float] = None
    continuity_source: str = "reference_image"
    edit_transition: str = "cut"
    status: str = "draft"
    
    class Config:
        from_attributes = True

class PromptBundleResponse(BaseModel):
    id: int
    shot_id: Optional[int] = None
    positive_prompt: str
    negative_prompt: Optional[str] = ""
    model_params: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    
    class Config:
        from_attributes = True

class AssetVersionResponse(BaseModel):
    id: int
    asset_type: str
    shot_id: Optional[int] = None
    file_path: str
    thumbnail_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_selected: bool = False
    created_at: datetime
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class GenerationJobResponse(BaseModel):
    id: int
    job_type: str
    status: str
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 2
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class ContinuityCheckResponse(BaseModel):
    valid: bool
    reason: str
    depends_on: Optional[int] = None
    version_id: Optional[int] = None
