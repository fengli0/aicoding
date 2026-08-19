# FFmpeg service for video processing, audio mixing, and final compositing
import subprocess
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from ..core.config import settings

class FFmpegService:
    def __init__(self, ffmpeg_path: str = None):
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH
    
    def _run_ffmpeg(self, args: List[str], timeout: int = 3600) -> subprocess.CompletedProcess:
        """Run FFmpeg command with given arguments"""
        cmd = [self.ffmpeg_path] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            return result
        except subprocess.TimeoutExpired:
            raise Exception(f"FFmpeg command timed out after {timeout} seconds")
        except Exception as e:
            raise Exception(f"FFmpeg error: {str(e)}")
    
    async def _run_ffmpeg_async(self, args: List[str], timeout: int = 3600) -> str:
        """Run FFmpeg command asynchronously"""
        cmd = [self.ffmpeg_path] + args
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg error: {stderr.decode()}")
            
            return stdout.decode() if stdout else ""
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise Exception(f"FFmpeg command timed out after {timeout} seconds")
    
    def probe_video(self, video_path: str) -> Dict[str, Any]:
        """Get video information using ffprobe"""
        cmd = [
            self.ffmpeg_path.replace("ffmpeg", "ffprobe"),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            return json.loads(result.stdout)
        except Exception as e:
            raise Exception(f"FFprobe error: {str(e)}")
    
    def extract_frame(self, video_path: str, output_path: str, timestamp: float = 0.0) -> bool:
        """Extract a single frame from video at given timestamp"""
        args = [
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            "-y",
            output_path
        ]
        
        result = self._run_ffmpeg(args)
        return result.returncode == 0
    
    def extract_last_frame(self, video_path: str, output_path: str) -> bool:
        """Extract the last frame from a video"""
        # First get video duration
        info = self.probe_video(video_path)
        duration = float(info.get("format", {}).get("duration", 0))
        
        # Extract frame near the end (95% of duration to avoid black frames)
        timestamp = max(0, duration - 0.5)
        return self.extract_frame(video_path, output_path, timestamp)
    
    def normalize_video(
        self,
        input_path: str,
        output_path: str,
        target_width: int = 1920,
        target_height: int = 1080,
        target_fps: int = 25,
        pixel_format: str = "yuv420p"
    ) -> bool:
        """Normalize video to target specifications"""
        args = [
            "-i", input_path,
            "-vf", f"scale={target_width}:{target_height},fps={target_fps}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", pixel_format,
            "-c:a", "aac",
            "-ar", "48000",
            "-y",
            output_path
        ]
        
        result = self._run_ffmpeg(args)
        return result.returncode == 0
    
    def concatenate_videos(
        self,
        video_paths: List[str],
        output_path: str,
        transitions: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Concatenate multiple videos with optional transitions"""
        if not video_paths:
            return False
        
        if len(video_paths) == 1:
            # Just copy single video
            args = ["-i", video_paths[0], "-c", "copy", "-y", output_path]
            result = self._run_ffmpeg(args)
            return result.returncode == 0
        
        # Create concat file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")
            concat_file = f.name
        
        try:
            args = [
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y",
                output_path
            ]
            
            result = self._run_ffmpeg(args)
            return result.returncode == 0
        finally:
            import os
            os.unlink(concat_file)
    
    def add_transition(
        self,
        input1: str,
        input2: str,
        output_path: str,
        transition_type: str = "cut",
        duration: float = 0.5
    ) -> bool:
        """Add transition between two videos"""
        if transition_type == "cut":
            # Simple concatenation
            return self.concatenate_videos([input1, input2], output_path)
        
        elif transition_type == "dissolve":
            args = [
                "-i", input1,
                "-i", input2,
                "-filter_complex",
                f"[0][1]xfade=transition=dissolve:duration={duration}:offset={duration}",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-y",
                output_path
            ]
            
            result = self._run_ffmpeg(args)
            return result.returncode == 0
        
        elif transition_type in ["fade_in", "fade_out"]:
            # Apply fade filter
            if transition_type == "fade_in":
                filter_str = f"fade=in:duration={duration}"
            else:
                filter_str = f"fade=out:duration={duration}"
            
            input_video = input1 if transition_type == "fade_in" else input2
            args = [
                "-i", input_video,
                "-vf", filter_str,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-y",
                output_path
            ]
            
            result = self._run_ffmpeg(args)
            return result.returncode == 0
        
        return False
    
    def mix_audio(
        self,
        audio_paths: List[str],
        output_path: str,
        volumes: Optional[List[float]] = None,
        ducking: bool = False
    ) -> bool:
        """Mix multiple audio tracks with optional ducking"""
        if not audio_paths:
            return False
        
        if len(audio_paths) == 1:
            args = ["-i", audio_paths[0], "-c:a", "aac", "-y", output_path]
            result = self._run_ffmpeg(args)
            return result.returncode == 0
        
        # Build complex filter for mixing
        inputs = []
        for path in audio_paths:
            inputs.extend(["-i", path])
        
        filter_parts = []
        for i, path in enumerate(audio_paths):
            vol = volumes[i] if volumes and i < len(volumes) else 1.0
            filter_parts.append(f"[{i}:a]volume={vol}[a{i}]")
        
        mix_inputs = "".join([f"[a{i}]" for i in range(len(audio_paths))])
        filter_parts.append(f"{mix_inputs}amix=inputs={len(audio_paths)}:duration=longest[aout]")
        
        filter_complex = ";".join(filter_parts)
        
        args = inputs + [
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-c:a", "aac",
            "-ar", "48000",
            "-y",
            output_path
        ]
        
        result = self._run_ffmpeg(args)
        return result.returncode == 0
    
    def add_background_music(
        self,
        dialogue_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.3,
        dialogue_volume: float = 1.0
    ) -> bool:
        """Add background music with ducking under dialogue"""
        args = [
            "-i", dialogue_path,
            "-i", bgm_path,
            "-filter_complex",
            f"[0:a]volume={dialogue_volume}[dialogue];[1:a]volume={bgm_volume}[bgm];[dialogue][bgm]amix=inputs=2:duration=first",
            "-c:a", "aac",
            "-ar", "48000",
            "-y",
            output_path
        ]
        
        result = self._run_ffmpeg(args)
        return result.returncode == 0
    
    def burn_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        font_size: int = 24,
        font_color: str = "white"
    ) -> bool:
        """Burn subtitles into video"""
        # Escape colons in path for filter
        subtitle_escaped = subtitle_path.replace(":", "\\:")
        
        args = [
            "-i", video_path,
            "-vf", f"subtitles={subtitle_escaped}:fontsize={font_size}:fontcolor={font_color}",
            "-c:a", "copy",
            "-y",
            output_path
        ]
        
        result = self._run_ffmpeg(args)
        return result.returncode == 0
    
    def generate_srt(
        self,
        timestamps: List[Dict[str, Any]],
        output_path: str
    ) -> bool:
        """Generate SRT subtitle file from timestamps"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, ts in enumerate(timestamps, 1):
                    start = self._format_srt_time(ts['start'])
                    end = self._format_srt_time(ts['end'])
                    text = ts.get('text', ts.get('word', ''))
                    
                    f.write(f"{i}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
            
            return True
        except Exception:
            return False
    
    def _format_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def composite_final_video(
        self,
        video_clips: List[Dict[str, Any]],
        audio_tracks: List[Dict[str, Any]],
        subtitle_path: Optional[str],
        output_path: str,
        burn_subtitles: bool = True
    ) -> bool:
        """Composite final video with all clips, audio tracks, and subtitles"""
        # This is a simplified implementation
        # In production, this would handle complex multi-track compositing
        
        # First concatenate all video clips
        temp_video = output_path.replace(".mp4", "_temp.mp4")
        video_paths = [clip['path'] for clip in video_clips]
        
        if not self.concatenate_videos(video_paths, temp_video):
            return False
        
        # Mix all audio tracks
        temp_audio = output_path.replace(".mp4", "_temp.wav")
        audio_paths = [track['path'] for track in audio_tracks]
        audio_volumes = [track.get('volume', 1.0) for track in audio_tracks]
        
        if not self.mix_audio(audio_paths, temp_audio, audio_volumes):
            return False
        
        # Combine video and audio
        args = [
            "-i", temp_video,
            "-i", temp_audio,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-ar", "48000",
            "-shortest",
            "-y",
            output_path
        ]
        
        if burn_subtitles and subtitle_path:
            subtitle_escaped = subtitle_path.replace(":", "\\:")
            args.insert(3, "-vf")
            args.insert(4, f"subtitles={subtitle_escaped}")
        
        result = self._run_ffmpeg(args)
        
        # Cleanup temp files
        import os
        try:
            os.unlink(temp_video)
            os.unlink(temp_audio)
        except:
            pass
        
        return result.returncode == 0
    
    def export_with_specs(
        self,
        input_path: str,
        output_path: str,
        target_width: int = 1920,
        target_height: int = 1080,
        target_fps: int = 25,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        audio_sample_rate: int = 48000,
        pixel_format: str = "yuv420p"
    ) -> bool:
        """Export video with specific codec and format requirements"""
        args = [
            "-i", input_path,
            "-vf", f"scale={target_width}:{target_height},fps={target_fps}",
            "-c:v", video_codec,
            "-preset", "slow",
            "-crf", "18",
            "-pix_fmt", pixel_format,
            "-c:a", audio_codec,
            "-ar", str(audio_sample_rate),
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        result = self._run_ffmpeg(args)
        return result.returncode == 0
