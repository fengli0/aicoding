# FFmpeg utility for video processing
import subprocess
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from ..core.config import settings

class FFmpegService:
    def __init__(self, ffmpeg_path: str = None):
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH
    
    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video information using ffprobe"""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return {}
    
    def extract_last_frame(self, video_path: str, output_path: str) -> bool:
        """Extract the last frame from a video"""
        try:
            # First get video duration
            info = self.get_video_info(video_path)
            if not info:
                return False
            
            duration = float(info.get("format", {}).get("duration", 0))
            if duration <= 0:
                return False
            
            # Extract frame at 99% of duration to ensure we get the last complete frame
            timestamp = duration * 0.99
            
            cmd = [
                self.ffmpeg_path,
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except Exception:
            return False
    
    def normalize_video(
        self,
        input_path: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 25,
        codec: str = "libx264",
        pixel_format: str = "yuv420p"
    ) -> bool:
        """Normalize video to target specs"""
        try:
            cmd = [
                self.ffmpeg_path,
                "-i", input_path,
                "-vf", f"scale={width}:{height},fps={fps}",
                "-c:v", codec,
                "-pix_fmt", pixel_format,
                "-c:a", "aac",
                "-ar", "48000",
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception:
            return False
    
    def merge_videos(
        self,
        video_paths: List[str],
        output_path: str,
        transitions: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Merge multiple videos with optional transitions"""
        try:
            if not video_paths:
                return False
            
            if len(video_paths) == 1:
                # Just copy single video
                cmd = [
                    self.ffmpeg_path,
                    "-i", video_paths[0],
                    "-c", "copy",
                    "-y",
                    output_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                return result.returncode == 0
            
            # Create concat file
            concat_file = Path(output_path).with_suffix(".txt")
            with open(concat_file, 'w') as f:
                for path in video_paths:
                    f.write(f"file '{path}'\n")
            
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Clean up concat file
            try:
                concat_file.unlink()
            except Exception:
                pass
            
            return result.returncode == 0
        except Exception:
            return False
    
    def add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        volume: float = 1.0,
        fade_duration: float = 0.5
    ) -> bool:
        """Add/replace audio track in video"""
        try:
            audio_filter = f"volume={volume}"
            if fade_duration > 0:
                audio_filter += f",afade=t=out:st={fade_duration}:d={fade_duration}"
            
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-i", audio_path,
                "-vf", f"afade=t=in:st=0:d={fade_duration}",
                "-filter_complex", f"[1:a]{audio_filter}[a]",
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-ar", "48000",
                "-shortest",
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception:
            return False
    
    def generate_srt(
        self,
        subtitles: List[Dict[str, Any]],
        output_path: str
    ) -> bool:
        """Generate SRT subtitle file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, 1):
                    start = self._format_srt_time(sub["start"])
                    end = self._format_srt_time(sub["end"])
                    text = sub["text"]
                    
                    f.write(f"{i}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
            return True
        except Exception:
            return False
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time in SRT format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def burn_subtitles(
        self,
        video_path: str,
        srt_path: str,
        output_path: str
    ) -> bool:
        """Burn subtitles into video"""
        try:
            # Escape quotes in path for filter
            srt_path_escaped = srt_path.replace("'", "'\\''")
            
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-vf", f"subtitles='{srt_path_escaped}'",
                "-c:a", "copy",
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception:
            return False
    
    def mix_audio_tracks(
        self,
        tracks: List[Dict[str, Any]],  # [{path, volume, start_time}]
        output_path: str,
        duration: float
    ) -> bool:
        """Mix multiple audio tracks"""
        try:
            if not tracks:
                return False
            
            # Build filter complex for mixing
            inputs = []
            filter_parts = []
            
            for i, track in enumerate(tracks):
                inputs.extend(["-i", track["path"]])
                
                vol = track.get("volume", 1.0)
                start = track.get("start_time", 0)
                
                filter_parts.append(f"[{i}:a]volume={vol},adelay={int(start*1000)}[a{i}]")
            
            # Mix all tracks
            mix_inputs = "".join([f"[a{i}]" for i in range(len(tracks))])
            filter_parts.append(f"{mix_inputs}amix=inputs={len(tracks)}:duration=longest[out]")
            
            filter_complex = ";".join(filter_parts)
            
            cmd = [
                self.ffmpeg_path,
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[out]",
                "-c:a", "aac",
                "-ar", "48000",
                "-t", str(duration),
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception:
            return False
