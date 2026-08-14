"""
Video concatenation and output nodes for ComfyUI-PixellePost plugin.

Nodes:
- PixelleConcatVideo: Concatenate multiple video assets with optional BGM
- PixelleSaveVideo: Save final video to ComfyUI output directory
"""

import json
import os
import shutil
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path


class PixelleConcatVideo:
    """
    Concatenate multiple video assets with optional BGM mixing.
    
    This node handles:
    - Format normalization across segments
    - Seamless concatenation
    - BGM mixing with volume control
    """
    
    CATEGORY = "Pixelle/Batch"
    FUNCTION = "concat_video"
    RETURN_TYPES = ("PIXELLE_VIDEO", "STRING")
    RETURN_NAMES = ("video_asset", "video_path")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_paths_json": ("STRING", {"multiline": True}),
            },
            "optional": {
                "bgm_audio": ("AUDIO",),
                "bgm_path": ("STRING", {"multiline": False, "default": ""}),
                "bgm_volume": ("FLOAT", {"default": 0.20, "min": 0.0, "max": 1.0}),
                "voice_volume": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
                "output_dir": ("STRING", {"multiline": False, "default": ""}),
                "filename_prefix": ("STRING", {"multiline": False, "default": "pixelle_final"}),
            }
        }
    
    def concat_video(
        self,
        video_paths_json: str,
        bgm_audio: Optional[Tuple] = None,
        bgm_path: str = "",
        bgm_volume: float = 0.20,
        voice_volume: float = 1.0,
        output_dir: str = "",
        filename_prefix: str = "pixelle_final",
    ) -> Tuple[Dict[str, Any], str]:
        """
        Concatenate videos with optional BGM.
        
        Args:
            video_paths_json: JSON array of video paths or video asset dicts
            bgm_audio: ComfyUI AUDIO tuple (waveform, sample_rate)
            bgm_path: Path to BGM file
            bgm_volume: BGM volume (0.0-1.0)
            voice_volume: Voice/narration volume (0.0-1.0)
            output_dir: Output directory
            filename_prefix: Output filename prefix
            
        Returns:
            Tuple of (video asset dict, video path)
        """
        from ..core.ffmpeg_service import FfmpegService
        
        # Parse video paths
        data = json.loads(video_paths_json)
        
        if isinstance(data, list):
            video_paths = []
            for item in data:
                if isinstance(item, dict) and "path" in item:
                    video_paths.append(item["path"])
                elif isinstance(item, str):
                    video_paths.append(item)
                else:
                    raise ValueError(f"Invalid video path item: {item}")
        else:
            raise ValueError("video_paths_json must be a JSON array")
        
        if not video_paths:
            raise ValueError("At least one video path is required")
        
        # Determine BGM path
        actual_bgm_path = bgm_path
        if bgm_audio is not None:
            # In real implementation, convert audio tensor to temp WAV
            raise NotImplementedError("BGM from AUDIO tensor requires adapter")
        
        # Determine output directory
        if not output_dir:
            try:
                import folder_paths
                output_dir = folder_paths.get_output_directory()
            except ImportError:
                output_dir = os.path.join(os.getcwd(), "output")
        
        # Sanitize filename prefix
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in '._-')
        if not safe_prefix:
            safe_prefix = "pixelle_final"
        
        output_path = os.path.join(output_dir, f"{safe_prefix}.mp4")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Initialize FFmpeg service
        ffmpeg = FfmpegService()
        
        # Concatenate videos
        media_info = ffmpeg.concat_videos(
            video_paths=video_paths,
            output_path=output_path,
            bgm_path=actual_bgm_path if actual_bgm_path else None,
            bgm_volume=bgm_volume,
            voice_volume=voice_volume,
        )
        
        # Build video asset
        video_asset = {
            "path": output_path,
            "duration": media_info.duration,
            "width": media_info.width,
            "height": media_info.height,
            "fps": media_info.fps,
        }
        
        return (video_asset, output_path)


class PixelleSaveVideo:
    """
    Save final video to ComfyUI output directory.
    
    This is an OUTPUT_NODE that ensures the video is properly
    saved and available for preview in the ComfyUI interface.
    """
    
    CATEGORY = "Pixelle/Output"
    FUNCTION = "save_video"
    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_asset_json": ("STRING", {"multiline": True}),
                "filename_prefix": ("STRING", {"multiline": False, "default": "pixelle"}),
            },
            "optional": {
                "output_subdir": ("STRING", {"multiline": False, "default": ""}),
            }
        }
    
    def save_video(
        self,
        video_asset_json: str,
        filename_prefix: str,
        output_subdir: str = "",
    ) -> Tuple[str]:
        """
        Save video to ComfyUI output.
        
        Args:
            video_asset_json: JSON representation of video asset
            filename_prefix: Output filename prefix
            output_subdir: Optional subdirectory within output
            
        Returns:
            Tuple of (video path,)
        """
        # Parse video asset
        video_asset = json.loads(video_asset_json)
        source_path = video_asset.get("path", "")
        
        if not source_path or not os.path.exists(source_path):
            raise ValueError(f"Source video does not exist: {source_path}")
        
        # Determine output directory
        try:
            import folder_paths
            base_output_dir = folder_paths.get_output_directory()
        except ImportError:
            base_output_dir = os.path.join(os.getcwd(), "output")
        
        if output_subdir:
            # Sanitize subdirectory name
            safe_subdir = "".join(c for c in output_subdir if c.isalnum() or c in '._-/')
            output_dir = os.path.join(base_output_dir, safe_subdir)
        else:
            output_dir = base_output_dir
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Sanitize filename prefix
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in '._-')
        if not safe_prefix:
            safe_prefix = "pixelle"
        
        # Generate unique filename
        import hashlib
        import time
        timestamp = int(time.time())
        hash_input = f"{safe_prefix}-{timestamp}-{source_path}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        
        filename = f"{safe_prefix}_{hash_suffix}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        # Copy file to output
        shutil.copy2(source_path, output_path)
        
        return (output_path,)
