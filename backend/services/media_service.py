import os
import shutil
import subprocess
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import AssetVersion, GenerationJob
from core.config import settings

class FFmpegService:
    """FFmpeg 包装服务，负责媒体处理、标准化和合成"""

    def __init__(self):
        self.ffmpeg_path = "ffmpeg"  # 假设已加入环境变量，或可配置绝对路径
        self.ffprobe_path = "ffprobe"

    def check_ffmpeg_installed(self) -> bool:
        """检查 FFmpeg 是否可用"""
        try:
            subprocess.run([self.ffmpeg_path, "-version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def extract_last_frame(self, input_video: str, output_image: str) -> bool:
        """抽取视频最后一帧作为连续性参考"""
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-vf", "select=eq(n\\,${{stream_size-1}}),scale=1920:1080",
            "-vframes", "1",
            "-y",
            output_image
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_image)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg extract frame failed: {e}")
            return False

    def normalize_video(
        self, 
        input_video: str, 
        output_video: str,
        target_resolution: tuple = (1920, 1080),
        target_fps: int = 25,
        pixel_format: str = "yuv420p"
    ) -> bool:
        """将视频标准化为指定规格 (缩放/补边 + 帧率转换 + 像素格式)"""
        w, h = target_resolution
        
        # 使用 scale 和 pad 滤镜保持比例并补黑边
        filter_complex = f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-vf", filter_complex,
            "-r", str(target_fps),
            "-pix_fmt", pixel_format,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_video
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_video)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg normalize failed: {e}")
            return False

    def get_video_duration(self, video_path: str) -> float:
        """获取视频时长 (秒)"""
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0.0

    def merge_audio_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        fade_out_ms: int = 0
    ) -> bool:
        """合并视频和音频轨道，支持简单的淡出"""
        filters = []
        if fade_out_ms > 0:
            filters.append(f"afade=t=out:st={fade_out_ms/1000}:d={fade_out_ms/1000}")
            
        filter_str = ",".join(filters) if filters else "anull"

        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_str,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            "-y",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_path)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg merge A/V failed: {e}")
            return False

    def generate_srt_from_cues(
        self,
        cues: List[Dict[str, Any]],
        output_path: str
    ) -> bool:
        """根据时间轴提示生成 SRT 字幕文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, cue in enumerate(cues, 1):
                    start = self._format_srt_time(cue['start'])
                    end = self._format_srt_time(cue['end'])
                    text = cue['text']
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            return True
        except Exception as e:
            print(f"Generate SRT failed: {e}")
            return False

    def _format_srt_time(self, seconds: float) -> str:
        """将秒数转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds * 1000) % 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def burn_subtitles(
        self,
        input_video: str,
        subtitle_srt: str,
        output_video: str
    ) -> bool:
        """烧录硬字幕到视频"""
        # Windows 路径需要转义反斜杠
        subtitle_path_escaped = subtitle_srt.replace("\\", "/").replace(":", r"\:")
        
        filter_complex = f"subtitles='{subtitle_path_escaped}'"
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_video,
            "-vf", filter_complex,
            "-c:a", "copy",
            "-y",
            output_video
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_video)
        except subprocess.CalledProcessError as e:
            print(f"Burn subtitles failed: {e}")
            return False

    def mix_audio_tracks(
        self,
        tracks: List[Dict[str, Any]],  # [{path, volume, type}]
        output_path: str,
        ducking_db: float = -10.0  # 对白闪避时的降低分贝数
    ) -> bool:
        """混合多轨音频 (BGM + 音效 + 对白)，支持闪避"""
        # 构建复杂的 filter_complex 实现闪避
        # 简化版：直接按音量混合，实际需根据时间轴做动态闪避
        inputs = []
        filter_parts = []
        
        for i, track in enumerate(tracks):
            inputs.extend(["-i", track['path']])
            vol = track.get('volume', 1.0)
            filter_parts.append(f"[{i}:a]volume={vol}[a{i}]")
            
        # 简单混合所有轨道
        mix_inputs = "".join([f"[a{i}]" for i in range(len(tracks))])
        filter_parts.append(f"{mix_inputs}amix=inputs={len(tracks)}:duration=longest[out]")
        
        filter_complex = ";".join(filter_parts)
        
        cmd = [
            self.ffmpeg_path,
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_path)
        except subprocess.CalledProcessError as e:
            print(f"Mix audio failed: {e}")
            return False
