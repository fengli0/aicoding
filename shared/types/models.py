"""
核心数据类型定义
所有生成版本记录模型、工作流版本、参数、seed、输入素材、依赖版本、创建时间和错误信息
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


class StageStatus(str, Enum):
    """阶段状态统一枚举"""
    DRAFT = "draft"           # 草稿
    PENDING_REVIEW = "pending_review"  # 待审核
    APPROVED = "approved"     # 已通过
    GENERATING = "generating" # 生成中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    EXPIRED = "expired"       # 已过期


class EditTransition(str, Enum):
    """剪辑转场类型"""
    CUT = "cut"               # 硬切
    DISSOLVE = "dissolve"     # 叠化
    FADE_IN = "fade_in"       # 淡入
    FADE_OUT = "fade_out"     # 淡出
    FADE_IN_OUT = "fade_in_out"  # 淡入淡出
    WIPE = "wipe"             # 擦除


class ShotSize(str, Enum):
    """景别类型"""
    EXTREME_LONG = "extreme_long"      # 大远景
    LONG = "long"                      # 远景
    FULL = "full"                      # 全景
    MEDIUM_LONG = "medium_long"        # 中全景
    MEDIUM = "medium"                  # 中景
    MEDIUM_CLOSE = "medium_close"      # 中近景
    CLOSE_UP = "close_up"              # 近景
    EXTREME_CLOSE_UP = "extreme_close_up"  # 特写


class CameraMovement(str, Enum):
    """运镜方式"""
    STATIC = "static"           # 固定
    PAN_LEFT = "pan_left"       # 左摇
    PAN_RIGHT = "pan_right"     # 右摇
    TILT_UP = "tilt_up"         # 上摇
    TILT_DOWN = "tilt_down"     # 下摇
    ZOOM_IN = "zoom_in"         # 推镜头
    ZOOM_OUT = "zoom_out"       # 拉镜头
    DOLLY_IN = "dolly_in"       # 前移
    DOLLY_OUT = "dolly_out"     # 后移
    TRACKING = "tracking"       # 跟随
    HANDHELD = "handheld"       # 手持


@dataclass
class Project:
    """项目数据结构"""
    id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: StageStatus = StageStatus.DRAFT
    episode_count: int = 0
    current_episode: int = 1
    production_stage: str = "novel"  # novel, script, storyboard, asset, video, audio, composite
    task_progress: float = 0.0
    disk_usage_mb: float = 0.0
    last_error: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    
    # 输出规格
    resolution_width: int = 1920
    resolution_height: int = 1080
    aspect_ratio: str = "16:9"
    fps: int = 25
    target_duration_min: int = 3
    target_duration_max: int = 8


@dataclass
class Episode:
    """分集数据结构"""
    id: str
    project_id: str
    episode_number: int
    title: str = ""
    summary: str = ""
    core_conflict: str = ""
    status: StageStatus = StageStatus.DRAFT
    script_status: StageStatus = StageStatus.DRAFT
    storyboard_status: StageStatus = StageStatus.DRAFT
    asset_status: StageStatus = StageStatus.DRAFT
    video_status: StageStatus = StageStatus.DRAFT
    audio_status: StageStatus = StageStatus.DRAFT
    composite_status: StageStatus = StageStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EntityProfile:
    """实体档案 - 人物、场景、道具的统一定义"""
    id: str
    project_id: str
    entity_type: str  # character, scene, prop
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    prompt_base: str = ""  # 基础提示词
    negative_prompt: str = ""
    model_params: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EntityVariant:
    """实体变体 - 人物造型、场景变体、道具状态等"""
    id: str
    entity_id: str
    variant_type: str  # costume, injury, age, day_night, etc.
    name: str = ""
    description: str = ""
    prompt_modifiers: List[str] = field(default_factory=list)
    reference_image_id: Optional[str] = None
    is_locked: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ScriptScene:
    """剧本场次"""
    id: str
    episode_id: str
    scene_number: int
    location: str = ""
    time_of_day: str = ""  # 日/夜/晨/昏
    interior_exterior: str = "INT"  # INT/EXT
    characters: List[str] = field(default_factory=list)
    costumes: Dict[str, str] = field(default_factory=dict)  # character -> costume
    props: List[str] = field(default_factory=list)
    actions: str = ""
    dialogues: List[Dict[str, Any]] = field(default_factory=list)  # {character, text, emotion, duration}
    narration: str = ""
    audio_requirements: List[str] = field(default_factory=list)
    status: StageStatus = StageStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Shot:
    """分镜镜头"""
    id: str
    scene_id: str
    shot_number: int
    shot_size: ShotSize = ShotSize.MEDIUM
    camera_position: str = ""
    camera_movement: CameraMovement = CameraMovement.STATIC
    action: str = ""
    dialogue: str = ""
    narration: str = ""
    estimated_duration: float = 0.0  # 秒
    frame_start_state: str = ""
    frame_end_state: str = ""
    
    # 连续性控制
    continuity_source: str = "auto"  # auto, previous_frame, reference_image
    continuity_ref_shot_id: Optional[str] = None
    
    # 剪辑转场
    edit_transition: EditTransition = EditTransition.CUT
    transition_duration: float = 0.0
    
    # 关联实体
    characters: List[str] = field(default_factory=list)
    scene_ref: Optional[str] = None  # 场景参考图 ID
    prop_refs: List[str] = field(default_factory=list)
    
    status: StageStatus = StageStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PromptBundle:
    """提示词包 - 组合实体提示词生成镜头提示词"""
    id: str
    shot_id: str
    
    # 锁定的实体提示词
    character_prompts: Dict[str, str] = field(default_factory=dict)  # character_id -> prompt
    scene_prompt: str = ""
    prop_prompts: Dict[str, str] = field(default_factory=dict)
    
    # 镜头提示词
    shot_prompt: str = ""
    full_prompt: str = ""
    negative_prompt: str = ""
    
    # 模型参数
    model_name: str = ""
    model_params: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssetVersion:
    """素材版本 - 图片、视频、音频的版本管理"""
    id: str
    asset_type: str  # image, video, audio
    entity_id: Optional[str] = None  # 关联实体
    shot_id: Optional[str] = None    # 关联镜头
    
    version_number: int = 1
    file_path: str = ""
    thumbnail_path: str = ""
    
    # 生成信息
    model_name: str = ""
    workflow_version: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    
    # 依赖关系
    input_assets: List[str] = field(default_factory=list)  # 输入素材版本 IDs
    dependency_versions: List[str] = field(default_factory=list)  # 依赖版本 IDs
    
    # 状态
    status: StageStatus = StageStatus.DRAFT
    error_message: Optional[str] = None
    
    # 元数据
    width: int = 0
    height: int = 0
    duration: float = 0.0  # 视频/音频时长
    fps: int = 0
    
    created_at: datetime = field(default_factory=datetime.now)
    is_current: bool = False  # 是否为当前选用版本


@dataclass
class GenerationJob:
    """生成任务 - 后台持久化任务队列"""
    id: str
    job_type: str  # llm, image, video, tts, composite
    priority: int = 0
    project_id: str = ""
    episode_id: Optional[str] = None
    shot_id: Optional[str] = None
    asset_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    workflow_json: Optional[str] = None
    status: StageStatus = StageStatus.DRAFT
    progress: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    comfyui_job_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class TimelineClip:
    """时间线片段 - 合成工作台使用"""
    id: str
    track_type: str  # video, audio_dialogue, audio_bgm, audio_sfx, subtitle
    position: float = 0.0  # 时间轴位置（秒）
    duration: float = 0.0
    
    asset_version_id: Optional[str] = None
    shot_id: Optional[str] = None
    
    # 视频属性
    transition: EditTransition = EditTransition.CUT
    transition_duration: float = 0.0
    
    # 音频属性
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    
    # 字幕属性
    subtitle_text: str = ""
    subtitle_style: Dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExportJob:
    """导出任务"""
    id: str
    project_id: str
    episode_id: Optional[str] = None
    export_type: str = "episode"
    output_format: str = "mp4"
    include_subtitles: bool = True
    include_master: bool = True
    export_srt: bool = True
    resolution: str = "1920x1080"
    fps: int = 25
    codec: str = "h264"
    audio_codec: str = "aac"
    audio_sample_rate: int = 48000
    pixel_format: str = "yuv420p"
    status: StageStatus = StageStatus.DRAFT
    progress: float = 0.0
    error_message: Optional[str] = None
    output_files: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
