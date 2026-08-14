"""
FFmpeg service for video composition operations.

Pure FFmpeg wrapper with no ComfyUI dependencies.
Handles:
- Duration probing
- Image to video segment generation
- Video overlay with subtitles
- Audio/video duration alignment
- Video concatenation
- BGM mixing
"""

import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class MediaInfo:
    """Media file information from ffprobe."""
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    has_video: bool
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediaInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class FfmpegService:
    """
    Stateless FFmpeg service for video operations.
    
    All methods take explicit paths and parameters - no implicit
    directory or configuration dependencies.
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        
        # Verify FFmpeg is available
        if not self._check_ffmpeg():
            raise RuntimeError(
                f"FFmpeg not found at {ffmpeg_path}. "
                "Please install FFmpeg and ensure it's in your PATH."
            )
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _check_ffprobe(self) -> bool:
        """Check if ffprobe is available."""
        try:
            result = subprocess.run(
                [self.ffprobe_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def probe_media(self, path: str) -> MediaInfo:
        """
        Probe a media file to get its properties.
        
        Args:
            path: Path to the media file
            
        Returns:
            MediaInfo with duration, dimensions, fps, and stream info
        """
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {path}: {result.stderr}")
        
        data = json.loads(result.stdout)
        
        # Extract video stream info
        video_stream = None
        audio_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream
        
        duration = float(data.get("format", {}).get("duration", 0))
        
        width = 0
        height = 0
        fps = 0.0
        
        if video_stream:
            width = video_stream.get("width", 0)
            height = video_stream.get("height", 0)
            
            # Calculate FPS from codec_time_base or r_frame_rate
            if "r_frame_rate" in video_stream:
                fps_str = video_stream["r_frame_rate"]
                if "/" in fps_str:
                    num, den = map(int, fps_str.split("/"))
                    fps = num / den if den > 0 else 0.0
                else:
                    fps = float(fps_str)
        
        return MediaInfo(
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            has_audio=audio_stream is not None,
            has_video=video_stream is not None,
        )
    
    def image_to_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        width: int,
        height: int,
        fps: int = 24,
        fit_mode: str = "contain",
    ) -> MediaInfo:
        """
        Create a video from an image with audio.
        
        The image is scaled/cropped to match the target dimensions,
        and the video duration matches the audio duration.
        
        Args:
            image_path: Path to the input image
            audio_path: Path to the audio file
            output_path: Path for the output video
            width: Target width
            height: Target height
            fps: Frames per second
            fit_mode: 'contain', 'cover', or 'stretch'
        """
        # First, get audio duration
        audio_info = self.probe_media(audio_path)
        duration = audio_info.duration
        
        # Build scale filter based on fit mode
        if fit_mode == "stretch":
            scale_filter = f"scale={width}:{height}"
        elif fit_mode == "contain":
            scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        elif fit_mode == "cover":
            scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        else:
            raise ValueError(f"Invalid fit_mode: {fit_mode}")
        
        cmd = [
            self.ffmpeg_path,
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", scale_filter,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-shortest",
            "-t", str(duration),
            "-y",
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(300, int(duration * 2)),
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        return self.probe_media(output_path)
    
    def freeze_last_frame(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> MediaInfo:
        """
        Extend a video by freezing the last frame to match audio duration.
        
        Args:
            video_path: Path to the input video
            audio_path: Path to the audio file
            output_path: Path for the output video
        """
        video_info = self.probe_media(video_path)
        audio_info = self.probe_media(audio_path)
        
        video_duration = video_info.duration
        audio_duration = audio_info.duration
        
        if video_duration >= audio_duration:
            # Video is already long enough, just copy with audio
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(audio_duration),
                "-y",
                output_path,
            ]
        else:
            # Freeze last frame
            freeze_duration = audio_duration - video_duration
            
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex",
                f"[0:v]split[orig][freeze];[orig]trim=0:{video_duration}[v];[freeze]trim={video_duration}:{video_duration},format=yuv420p[f];[v][f]concat=n=2:v=1:a=0[outv]",
                "-map", "[outv]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(audio_duration),
                "-y",
                output_path,
            ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(300, int(audio_duration * 2)),
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        return self.probe_media(output_path)
    
    def add_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
    ) -> MediaInfo:
        """
        Burn subtitles into a video.
        
        Args:
            video_path: Path to the input video
            subtitle_path: Path to the ASS subtitle file
            output_path: Path for the output video
        """
        # Escape paths for ASS filter
        escaped_subtitle_path = subtitle_path.replace(":", "\\:").replace("'", "'\\''")
        
        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-vf", f"subtitles='{escaped_subtitle_path}'",
            "-c:a", "copy",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-y",
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        return self.probe_media(output_path)
    
    def replace_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> MediaInfo:
        """
        Replace the audio track of a video.
        
        Args:
            video_path: Path to the input video
            audio_path: Path to the new audio file
            output_path: Path for the output video
        """
        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v",
            "-map", "1:a",
            "-shortest",
            "-y",
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        return self.probe_media(output_path)
    
    def concat_videos(
        self,
        video_paths: List[str],
        output_path: str,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.20,
        voice_volume: float = 1.0,
    ) -> MediaInfo:
        """
        Concatenate multiple videos with optional BGM mixing.
        
        Args:
            video_paths: List of input video paths (must have same codec/params)
            output_path: Path for the output video
            bgm_path: Optional background music path
            bgm_volume: BGM volume (0.0-1.0)
            voice_volume: Voice/narration volume (0.0-1.0)
        """
        if len(video_paths) < 1:
            raise ValueError("At least one video path is required")
        
        if len(video_paths) == 1:
            # Single video, just copy with optional BGM
            if bgm_path:
                return self.mix_bgm(video_paths[0], bgm_path, output_path, bgm_volume, voice_volume)
            else:
                cmd = [
                    self.ffmpeg_path,
                    "-i", video_paths[0],
                    "-c", "copy",
                    "-y",
                    output_path,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed: {result.stderr}")
                return self.probe_media(output_path)
        
        # Create concat file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            concat_file = f.name
            for path in video_paths:
                f.write(f"file '{path}'\n")
        
        try:
            if bgm_path:
                # Concat with BGM mixing using filter complex
                inputs = ["-i", concat_file]
                
                filter_complex = (
                    f"[0:v]concat=n={len(video_paths)}:v=1:a=1[outv];"
                    f"[0:a]volume={voice_volume}[voice];"
                    f"[1:a]volume={bgm_volume},aloop=loop=-1:size=2e+09[bgm]"
                )
                
                cmd = [
                    self.ffmpeg_path,
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file,
                    "-i", bgm_path,
                    "-filter_complex", filter_complex,
                    "-map", "[outv]",
                    "-map", "[voice]",
                    "-map", "[bgm]",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    "-y",
                    output_path,
                ]
            else:
                # Simple concat without BGM
                cmd = [
                    self.ffmpeg_path,
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file,
                    "-c", "copy",
                    "-y",
                    output_path,
                ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            
            return self.probe_media(output_path)
        finally:
            import os
            try:
                os.unlink(concat_file)
            except OSError:
                pass
    
    def mix_bgm(
        self,
        video_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.20,
        voice_volume: float = 1.0,
    ) -> MediaInfo:
        """
        Mix background music with a video's audio.
        
        Args:
            video_path: Path to the video
            bgm_path: Path to the BGM file
            output_path: Path for the output video
            bgm_volume: BGM volume (0.0-1.0)
            voice_volume: Voice/narration volume (0.0-1.0)
        """
        video_info = self.probe_media(video_path)
        bgm_info = self.probe_media(bgm_path)
        
        filter_complex = (
            f"[0:a]volume={voice_volume}[voice];"
            f"[1:a]volume={bgm_volume},aloop=loop=-1:size=2e+09[bgm];"
            f"[voice][bgm]amix=inputs=2:duration=shortest:dropout_transition=2[outa]"
        )
        
        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-i", bgm_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-y",
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(300, int(video_info.duration * 2)),
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        return self.probe_media(output_path)
