"""
Video composition nodes for ComfyUI-PixellePost plugin.

Nodes:
- PixelleComposeScene: Compose a single scene from shot data
- PixelleComposeStoryboard: Batch compose multiple scenes
"""

import json
import os
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path

from ..core.dto import (
    Shot, Manifest, VideoAsset, FitMode, DurationPolicy, SubtitleRenderer,
)


class PixelleComposeScene:
    """
    Compose a single scene from shot data.
    
    This node handles:
    - Image to video conversion with audio
    - Video duration alignment (freeze or crop)
    - Subtitle burning
    - Audio replacement
    """
    
    CATEGORY = "Pixelle/Post"
    FUNCTION = "compose_scene"
    RETURN_TYPES = ("PIXELLE_VIDEO", "STRING")
    RETURN_NAMES = ("video_asset", "video_path")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "shot_json": ("STRING", {"multiline": True}),
                "subtitle_path": ("STRING", {"multiline": False}),
                "canvas_width": ("INT", {"default": 720, "min": 64, "max": 3840}),
                "canvas_height": ("INT", {"default": 1280, "min": 64, "max": 3840}),
                "fps": ("INT", {"default": 24, "min": 1, "max": 60}),
            },
            "optional": {
                "fit_mode": (["contain", "cover", "stretch"],),
                "duration_policy": (["audio", "shortest", "longest_freeze"],),
                "output_dir": ("STRING", {"multiline": False, "default": ""}),
            }
        }
    
    def compose_scene(
        self,
        shot_json: str,
        subtitle_path: str,
        canvas_width: int,
        canvas_height: int,
        fps: int,
        fit_mode: str = "contain",
        duration_policy: str = "audio",
        output_dir: str = "",
    ) -> Tuple[Dict[str, Any], str]:
        """
        Compose a single scene.
        
        Args:
            shot_json: JSON representation of a Shot object
            subtitle_path: Path to ASS subtitle file
            canvas_width: Output canvas width
            canvas_height: Output canvas height
            fps: Output FPS
            fit_mode: How to fit media to canvas
            duration_policy: How to handle duration mismatch
            output_dir: Output directory
            
        Returns:
            Tuple of (video asset dict, video path)
        """
        from ..core.ffmpeg_service import FfmpegService
        
        # Parse shot
        shot_data = json.loads(shot_json)
        shot = Shot.from_dict(shot_data)
        
        # Determine output directory
        if not output_dir:
            try:
                import folder_paths
                output_dir = folder_paths.get_temp_directory()
            except ImportError:
                output_dir = os.path.join(os.getcwd(), "temp")
        
        output_path = os.path.join(output_dir, f"scene_{shot.index:03d}.mp4")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Initialize FFmpeg service
        ffmpeg = FfmpegService()
        
        # Get audio path (in real implementation, this would be resolved)
        audio_path = shot.audio.path
        
        # Compose based on media type
        if shot.media.type.value == "image":
            # Image to video with audio
            # Note: In real implementation, image tensor would be converted to temp PNG first
            image_path = shot.media.path
            if image_path == "__IMAGE_TENSOR__":
                raise ValueError("Image tensor must be converted to file path first")
            
            ffmpeg.image_to_video(
                image_path=image_path,
                audio_path=audio_path,
                output_path=output_path,
                width=canvas_width,
                height=canvas_height,
                fps=fps,
                fit_mode=fit_mode,
            )
        else:
            # Video processing
            video_path = shot.media.path
            
            # First, replace audio if needed
            temp_path = output_path.replace(".mp4", "_temp.mp4")
            ffmpeg.replace_audio(
                video_path=video_path,
                audio_path=audio_path,
                output_path=temp_path,
            )
            
            # Then handle duration alignment
            if duration_policy == "longest_freeze":
                ffmpeg.freeze_last_frame(
                    video_path=temp_path,
                    audio_path=audio_path,
                    output_path=output_path,
                )
            else:
                # Just copy with new audio
                os.rename(temp_path, output_path)
        
        # Burn subtitles
        final_path = output_path.replace(".mp4", "_final.mp4")
        ffmpeg.add_subtitles(
            video_path=output_path,
            subtitle_path=subtitle_path,
            output_path=final_path,
        )
        
        # Clean up temp file
        if os.path.exists(output_path) and output_path != final_path:
            os.remove(output_path)
        
        # Rename final to output
        if final_path != output_path:
            os.rename(final_path, output_path)
        
        # Probe result
        media_info = ffmpeg.probe_media(output_path)
        
        # Build video asset
        video_asset = {
            "path": output_path,
            "duration": media_info.duration,
            "width": media_info.width,
            "height": media_info.height,
            "fps": media_info.fps,
        }
        
        return (video_asset, output_path)


class PixelleComposeStoryboard:
    """
    Batch compose multiple scenes from a manifest.
    
    This node processes all shots in a manifest sequentially,
    handling resume/reuse logic via JobStore.
    """
    
    CATEGORY = "Pixelle/Batch"
    FUNCTION = "compose_storyboard"
    RETURN_TYPES = ("PIXELLE_VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video_list", "manifest_json", "output_dir")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "manifest_json": ("STRING", {"multiline": True}),
                "resume_mode": (["reuse_completed", "rebuild_failed", "force_rebuild"],),
            },
            "optional": {
                "output_base": ("STRING", {"multiline": False, "default": ""}),
            }
        }
    
    def compose_storyboard(
        self,
        manifest_json: str,
        resume_mode: str = "reuse_completed",
        output_base: str = "",
    ) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Compose all scenes in a manifest.
        
        Args:
            manifest_json: Manifest JSON string
            resume_mode: How to handle existing shots
            output_base: Base output directory
            
        Returns:
            Tuple of (list of video assets, updated manifest JSON, output directory)
        """
        from ..core.job_store import JobStore
        from ..core.ffmpeg_service import FfmpegService
        from ..core.subtitle_service import SubtitleService
        from ..core.dto import ShotStatus
        
        # Parse manifest
        manifest = Manifest.from_json(manifest_json)
        
        # Determine output base
        if not output_base:
            try:
                import folder_paths
                output_base = folder_paths.get_output_directory()
            except ImportError:
                output_base = os.path.join(os.getcwd(), "output")
        
        # Initialize job store
        job_store = JobStore(base_output_dir=output_base, job_id=manifest.job_id)
        job_store.ensure_dirs()
        
        # Acquire lock
        if not job_store.acquire_lock():
            raise RuntimeError(f"Job {manifest.job_id} is already being processed")
        
        try:
            # Initialize or load state
            state = job_store.load_state()
            if state is None or resume_mode == "force_rebuild":
                state = job_store.init_state(manifest)
            
            # Save manifest
            job_store.save_manifest(manifest)
            
            # Initialize services
            ffmpeg = FfmpegService()
            subtitle_service = SubtitleService()
            
            video_assets = []
            
            # Process each shot
            for shot in manifest.shots:
                shot_key = str(shot.index)
                shot_state = state["shots"].get(shot_key, {})
                
                # Check if we can reuse
                if resume_mode == "reuse_completed":
                    # Compute input hash (simplified for now)
                    current_hash = f"{shot.media.path}-{shot.audio.path}"
                    
                    if job_store.can_reuse_shot(shot.index, current_hash):
                        # Reuse existing output
                        output_path = shot_state.get("output_path")
                        if output_path and os.path.exists(output_path):
                            media_info = ffmpeg.probe_media(output_path)
                            video_assets.append({
                                "path": output_path,
                                "duration": media_info.duration,
                                "width": media_info.width,
                                "height": media_info.height,
                                "fps": media_info.fps,
                            })
                            continue
                
                # Mark as running
                job_store.update_shot_state(
                    index=shot.index,
                    status=ShotStatus.RUNNING,
                )
                
                try:
                    # Generate subtitle
                    subtitle_path = str(job_store.get_subtitle_path(shot.index))
                    
                    style = shot.subtitle_style or manifest.subtitle_style
                    if style:
                        subtitle_service.generate_ass(
                            events=shot.subtitle,
                            style=style,
                            output_path=subtitle_path,
                            canvas_width=manifest.canvas.width,
                            canvas_height=manifest.canvas.height,
                        )
                    
                    # Compose scene
                    output_path = str(job_store.get_scene_path(shot.index))
                    
                    if shot.media.type.value == "image":
                        # In real implementation, convert image tensor to file first
                        raise NotImplementedError("Image-to-video requires adapter")
                    else:
                        # Video processing
                        temp_path = output_path.replace(".mp4", "_temp.mp4")
                        ffmpeg.replace_audio(
                            video_path=shot.media.path,
                            audio_path=shot.audio.path,
                            output_path=temp_path,
                        )
                        
                        # Handle duration
                        if manifest.duration_policy == DurationPolicy.LONGEST_FREEZE:
                            ffmpeg.freeze_last_frame(
                                video_path=temp_path,
                                audio_path=shot.audio.path,
                                output_path=output_path,
                            )
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        else:
                            os.rename(temp_path, output_path)
                    
                    # Burn subtitles
                    final_path = output_path.replace(".mp4", "_final.mp4")
                    ffmpeg.add_subtitles(
                        video_path=output_path,
                        subtitle_path=subtitle_path,
                        output_path=final_path,
                    )
                    
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(final_path, output_path)
                    
                    # Probe and update state
                    media_info = ffmpeg.probe_media(output_path)
                    job_store.update_shot_state(
                        index=shot.index,
                        status=ShotStatus.COMPLETED,
                        output_path=output_path,
                        duration=media_info.duration,
                        input_hash=f"{shot.media.path}-{shot.audio.path}",
                    )
                    
                    video_assets.append({
                        "path": output_path,
                        "duration": media_info.duration,
                        "width": media_info.width,
                        "height": media_info.height,
                        "fps": media_info.fps,
                    })
                    
                except Exception as e:
                    job_store.update_shot_state(
                        index=shot.index,
                        status=ShotStatus.FAILED,
                        error_message=str(e),
                    )
                    raise
            
            return (video_assets, manifest.to_json(), str(job_store.job_dir))
            
        finally:
            job_store.release_lock()
