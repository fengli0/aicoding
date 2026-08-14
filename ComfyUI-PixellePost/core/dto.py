"""
Core DTOs for PixellePost plugin

Shot, Shots, VideoAsset, Manifest and related data transfer objects.
These are pure data classes without any service dependencies.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class FitMode(str, Enum):
    CONTAIN = "contain"
    COVER = "cover"
    STRETCH = "stretch"


class DurationPolicy(str, Enum):
    AUDIO = "audio"
    SHORTEST = "shortest"
    LONGEST_FREEZE = "longest_freeze"


class SubtitleRenderer(str, Enum):
    ASS = "ass"
    HTML = "html"


class ResumeMode(str, Enum):
    REUSE_COMPLETED = "reuse_completed"
    REBUILD_FAILED = "rebuild_failed"
    FORCE_REBUILD = "force_rebuild"


class ShotStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubtitleStyle:
    """Global or per-shot subtitle style configuration."""
    font_name: str = "Microsoft YaHei"
    font_size: int = 42
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 3
    position: str = "bottom"
    margin_bottom: int = 120
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "font_name": self.font_name,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "outline_color": self.outline_color,
            "outline_width": self.outline_width,
            "position": self.position,
            "margin_bottom": self.margin_bottom,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleStyle":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TransitionConfig:
    """Transition configuration after a shot."""
    type: str = "cut"
    duration: float = 0.25
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "duration": self.duration}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransitionConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SubtitleEvent:
    """A single subtitle event with timing."""
    text: str
    start: float = 0.0
    end: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleEvent":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MediaConfig:
    """Media source configuration for a shot."""
    type: MediaType
    path: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type.value, "path": self.path}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediaConfig":
        media_type = MediaType(data["type"]) if isinstance(data["type"], str) else data["type"]
        return cls(type=media_type, path=data["path"])


@dataclass
class AudioConfig:
    """Audio source configuration for a shot."""
    path: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioConfig":
        return cls(path=data["path"])


@dataclass
class Shot:
    """
    A single shot/scene in the storyboard.
    
    Contains all necessary information to render one scene:
    - Media source (image or video)
    - Audio source (TTS or other)
    - Subtitle text and timing
    - Optional title
    - Transition to next shot
    """
    index: int
    media: MediaConfig
    audio: AudioConfig
    subtitle: List[SubtitleEvent]
    title: Optional[str] = None
    subtitle_style: Optional[SubtitleStyle] = None
    transition_after: Optional[TransitionConfig] = None
    
    # Runtime state (not serialized to manifest)
    status: ShotStatus = ShotStatus.PENDING
    output_path: Optional[str] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    input_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "index": self.index,
            "media": self.media.to_dict(),
            "audio": self.audio.to_dict(),
            "subtitle": [s.to_dict() for s in self.subtitle],
        }
        if self.title is not None:
            result["title"] = self.title
        if self.subtitle_style is not None:
            result["subtitle_style"] = self.subtitle_style.to_dict()
        if self.transition_after is not None:
            result["transition_after"] = self.transition_after.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Shot":
        media = MediaConfig.from_dict(data["media"])
        audio = AudioConfig.from_dict(data["audio"])
        
        # Subtitle can be a string or list of events
        subtitle_data = data["subtitle"]
        if isinstance(subtitle_data, str):
            subtitle = [SubtitleEvent(text=subtitle_data)]
        elif isinstance(subtitle_data, dict) and "text" in subtitle_data:
            # Single event as dict
            subtitle = [SubtitleEvent.from_dict(subtitle_data)]
        elif isinstance(subtitle_data, list):
            subtitle = [SubtitleEvent.from_dict(s) for s in subtitle_data]
        else:
            raise ValueError(f"Invalid subtitle format: {type(subtitle_data)}")
        
        title = data.get("title")
        
        subtitle_style = None
        if "subtitle_style" in data:
            subtitle_style = SubtitleStyle.from_dict(data["subtitle_style"])
        
        transition_after = None
        if "transition_after" in data:
            transition_after = TransitionConfig.from_dict(data["transition_after"])
        
        return cls(
            index=index_from_data(data),
            media=media,
            audio=audio,
            subtitle=subtitle,
            title=title,
            subtitle_style=subtitle_style,
            transition_after=transition_after,
        )


def index_from_data(data: Dict[str, Any]) -> int:
    """Extract index from shot data, ensuring it's an integer."""
    idx = data.get("index")
    if idx is None:
        raise ValueError("Shot index is required")
    return int(idx)


@dataclass
class CanvasConfig:
    """Canvas configuration for the final video."""
    width: int = 720
    height: int = 1280
    fps: int = 24
    
    def to_dict(self) -> Dict[str, Any]:
        return {"width": self.width, "height": self.height, "fps": self.fps}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BGMConfig:
    """Background music configuration."""
    path: Optional[str] = None
    volume: float = 0.20
    mode: str = "loop"  # loop, once, crop
    
    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "volume": self.volume, "mode": self.mode}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BGMConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Manifest:
    """
    Complete manifest for batch video composition.
    
    This is the primary external interface for batch processing.
    It can be generated by upstream ComfyUI nodes, loaded from file,
    or submitted via ComfyUI prompt API.
    """
    schema_version: int
    job_id: str
    canvas: CanvasConfig
    shots: List[Shot]
    subtitle_style: Optional[SubtitleStyle] = None
    bgm: Optional[BGMConfig] = None
    fit_mode: FitMode = FitMode.CONTAIN
    duration_policy: DurationPolicy = DurationPolicy.AUDIO
    subtitle_renderer: SubtitleRenderer = SubtitleRenderer.ASS
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "canvas": self.canvas.to_dict(),
            "shots": [s.to_dict() for s in self.shots],
            "fit_mode": self.fit_mode.value,
            "duration_policy": self.duration_policy.value,
            "subtitle_renderer": self.subtitle_renderer.value,
        }
        if self.subtitle_style is not None:
            result["subtitle_style"] = self.subtitle_style.to_dict()
        if self.bgm is not None:
            result["bgm"] = self.bgm.to_dict()
        return result
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        schema_version = data.get("schema_version", 1)
        if schema_version != 1:
            raise ValueError(f"Unsupported schema version: {schema_version}")
        
        canvas = CanvasConfig.from_dict(data.get("canvas", {}))
        
        # Parse global subtitle style
        subtitle_style = None
        if "subtitle_style" in data:
            subtitle_style = SubtitleStyle.from_dict(data["subtitle_style"])
        
        # Parse shots
        shots_data = data.get("shots", [])
        shots = []
        for shot_data in shots_data:
            shot = Shot.from_dict(shot_data)
            # Merge global subtitle style if not overridden
            if shot.subtitle_style is None and subtitle_style is not None:
                shot.subtitle_style = subtitle_style
            shots.append(shot)
        
        # Sort by index
        shots.sort(key=lambda s: s.index)
        
        # Validate continuous indices starting from 1
        for i, shot in enumerate(shots):
            if shot.index != i + 1:
                raise ValueError(f"Shot indices must be continuous starting from 1, got {shot.index} at position {i}")
        
        # Parse BGM
        bgm = None
        if "bgm" in data:
            bgm = BGMConfig.from_dict(data["bgm"])
        
        fit_mode = FitMode(data.get("fit_mode", "contain"))
        duration_policy = DurationPolicy(data.get("duration_policy", "audio"))
        subtitle_renderer = SubtitleRenderer(data.get("subtitle_renderer", "ass"))
        
        return cls(
            schema_version=schema_version,
            job_id=data.get("job_id", "default"),
            canvas=canvas,
            shots=shots,
            subtitle_style=subtitle_style,
            bgm=bgm,
            fit_mode=fit_mode,
            duration_policy=duration_policy,
            subtitle_renderer=subtitle_renderer,
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "Manifest":
        import json
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class VideoAsset:
    """
    A video asset with metadata.
    
    This is the runtime representation of a composed video,
    used for passing between nodes and for final output.
    """
    path: str
    duration: float
    width: int
    height: int
    fps: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
        }
