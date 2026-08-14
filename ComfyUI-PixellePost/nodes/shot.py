"""
Shot-related nodes for ComfyUI-PixellePost plugin.

Nodes:
- PixelleCreateShot: Create a single shot from media, audio, and subtitle
- PixelleBuildShots: Build a shots list from individual shots or manifest
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
import torch

try:
    import folder_paths
    COMFYUI_AVAILABLE = True
except ImportError:
    COMFYUI_AVAILABLE = False

from ..core.dto import (
    Shot, MediaConfig, AudioConfig, SubtitleEvent, 
    MediaType, SubtitleStyle, TransitionConfig,
)
from ..adapters.comfy_types import ComfyTypeAdapter


class PixelleCreateShot:
    """
    Create a single shot from media, audio, and subtitle information.
    
    This node normalizes one shot's worth of素材 and字幕信息 into a
    PIXELLE_SHOT object that can be passed to composition nodes.
    """
    
    CATEGORY = "Pixelle/Post"
    FUNCTION = "create_shot"
    RETURN_TYPES = ("PIXELLE_SHOT", "STRING")
    RETURN_NAMES = ("shot", "json")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "caption": ("STRING", {"multiline": True, "default": ""}),
                "index": ("INT", {"default": 1, "min": 1, "max": 9999}),
            },
            "optional": {
                "image": ("IMAGE",),
                "video_path": ("STRING", {"multiline": False, "default": ""}),
                "audio": ("AUDIO",),
                "audio_path": ("STRING", {"multiline": False, "default": ""}),
                "title": ("STRING", {"multiline": False, "default": ""}),
                "transition_type": (["cut", "fade"],),
                "transition_duration": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 5.0}),
            }
        }
    
    def create_shot(
        self,
        caption: str,
        index: int,
        image: Optional[torch.Tensor] = None,
        video_path: str = "",
        audio: Optional[Tuple[torch.Tensor, int]] = None,
        audio_path: str = "",
        title: str = "",
        transition_type: str = "cut",
        transition_duration: float = 0.25,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Create a shot DTO from inputs.
        
        Args:
            caption: Subtitle text for this shot
            index: Shot index (1-based)
            image: ComfyUI IMAGE tensor
            video_path: Path to video file
            audio: ComfyUI AUDIO tuple (waveform, sample_rate)
            audio_path: Path to audio file
            title: Optional title for this shot
            transition_type: Transition type after this shot
            transition_duration: Transition duration in seconds
            
        Returns:
            Tuple of (shot dict, JSON string)
        """
        # Validate media input - must have either image or video_path
        if image is None and not video_path:
            raise ValueError("Must provide either image or video_path")
        
        if image is not None and video_path:
            raise ValueError("Cannot provide both image and video_path")
        
        # Validate audio input - must have either audio or audio_path
        if audio is None and not audio_path:
            raise ValueError("Must provide either audio or audio_path")
        
        if audio is not None and audio_path:
            raise ValueError("Cannot provide both audio and audio_path")
        
        # Initialize adapter for converting tensors to files
        adapter = ComfyTypeAdapter()
        
        # Determine media type and path
        if image is not None:
            media_type = MediaType.IMAGE
            # Convert image tensor to temp PNG
            media_path = adapter.image_to_png(
                image_tensor=image,
                filename=f"shot_{index:03d}_image",
            )
        else:
            media_type = MediaType.VIDEO
            media_path = video_path
        
        # Determine audio path
        if audio is not None:
            waveform, sample_rate = audio
            audio_path = adapter.audio_to_wav(
                waveform=waveform,
                sample_rate=sample_rate,
                filename=f"shot_{index:03d}_audio",
            )
        
        # Create subtitle event
        subtitle_event = SubtitleEvent(text=caption.strip() or " ")
        
        # Create transition config
        transition = TransitionConfig(
            type=transition_type,
            duration=transition_duration,
        )
        
        # Create shot
        shot = Shot(
            index=index,
            media=MediaConfig(type=media_type, path=media_path),
            audio=AudioConfig(path=audio_path),
            subtitle=[subtitle_event],
            title=title.strip() if title.strip() else None,
            transition_after=transition,
        )
        
        # Convert to dict for passing
        shot_dict = shot.to_dict()
        shot_json = json.dumps(shot_dict, ensure_ascii=False)
        
        return (shot_dict, shot_json)


class PixelleBuildShots:
    """
    Build a shots list from individual shots or a manifest JSON.
    
    This node consolidates multiple PIXELLE_SHOT objects into an ordered
    PIXELLE_SHOTS list, validates continuity, and assigns stable job IDs.
    """
    
    CATEGORY = "Pixelle/Batch"
    FUNCTION = "build_shots"
    RETURN_TYPES = ("PIXELLE_SHOTS", "STRING")
    RETURN_NAMES = ("shots", "manifest_json")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "shots_input": ("STRING", {"multiline": True}),
            },
            "optional": {
                "job_id": ("STRING", {"multiline": False, "default": ""}),
                "width": ("INT", {"default": 720, "min": 64, "max": 3840}),
                "height": ("INT", {"default": 1280, "min": 64, "max": 3840}),
                "fps": ("INT", {"default": 24, "min": 1, "max": 60}),
            }
        }
    
    def build_shots(
        self,
        shots_input: str,
        job_id: str = "",
        width: int = 720,
        height: int = 1280,
        fps: int = 24,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Build a shots list from input.
        
        Args:
            shots_input: Either a JSON array of shots or a manifest JSON
            job_id: Optional job ID (auto-generated if empty)
            width: Canvas width
            height: Canvas height
            fps: Canvas FPS
            
        Returns:
            Tuple of (shots list, manifest JSON)
        """
        import hashlib
        from datetime import datetime
        
        data = json.loads(shots_input)
        
        # Check if this is a manifest or just shots array
        if isinstance(data, list):
            shots_data = data
        elif isinstance(data, dict) and "shots" in data:
            shots_data = data.get("shots", [])
        else:
            raise ValueError("Input must be a shots array or manifest object")
        
        # Parse shots
        shots = []
        for shot_data in shots_data:
            shot = Shot.from_dict(shot_data)
            shots.append(shot)
        
        # Sort by index
        shots.sort(key=lambda s: s.index)
        
        # Validate continuous indices starting from 1
        for i, shot in enumerate(shots):
            if shot.index != i + 1:
                raise ValueError(
                    f"Shot indices must be continuous starting from 1, "
                    f"got {shot.index} at position {i}"
                )
        
        # Generate job ID if not provided
        if not job_id:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            hash_input = f"{timestamp}-{len(shots)}-{width}x{height}@{fps}"
            job_id = f"pixelle-{hashlib.sha256(hash_input.encode()).hexdigest()[:8]}"
        
        # Build manifest
        from ..core.dto import Manifest, CanvasConfig
        
        manifest = Manifest(
            schema_version=1,
            job_id=job_id,
            canvas=CanvasConfig(width=width, height=height, fps=fps),
            shots=shots,
        )
        
        manifest_json = manifest.to_json()
        
        # Return shots list and manifest
        shots_list = [s.to_dict() for s in shots]
        
        return (shots_list, manifest_json)
