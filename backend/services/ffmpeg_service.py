"""
FFmpeg 服务
负责抽帧、标准化、混音和合成
"""

import asyncio
import json
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path


class FFmpegService:
    """FFmpeg 服务类"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
    
    async def run_command(self, args: List[str], timeout: Optional[float] = None) -> subprocess.CompletedProcess:
        """运行 FFmpeg 命令"""
        cmd = [self.ffmpeg_path] + args
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {stderr.decode()}")
            
            return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
            
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("FFmpeg command timed out")
    
    def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """获取媒体文件信息"""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe error: {result.stderr}")
        
        return json.loads(result.stdout)
    
    async def extract_frame(
        self,
        video_path: str,
        output_path: str,
        timestamp: float = 0.0,
        width: Optional[int] = None,
        height: Optional[int] = None
    ):
        """从视频中抽取指定时间点的帧"""
        args = [
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        
        if width and height:
            args.extend(["-vf", f"scale={width}:{height}"])
        
        await self.run_command(args)
    
    async def extract_last_frame(
        self,
        video_path: str,
        output_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None
    ):
        """抽取视频的最后一帧"""
        args = [
            "-i", video_path,
            "-vf", "select='eq(pict_type,I)+eq(n,n-1)'",
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        
        if width and height:
            args[-3:-3] = ["-vf", f"scale={width}:{height}"]
        
        await self.run_command(args)
    
    async def normalize_video(
        self,
        input_path: str,
        output_path: str,
        target_width: int = 1920,
        target_height: int = 1080,
        target_fps: int = 25,
        pixel_format: str = "yuv420p",
        codec: str = "h264"
    ):
        """标准化视频规格"""
        # 计算缩放和补边参数
        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease"
        pad_filter = f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2"
        
        args = [
            "-i", input_path,
            "-vf", f"{scale_filter},{pad_filter}",
            "-r", str(target_fps),
            "-pix_fmt", pixel_format,
            "-c:v", codec,
            "-c:a", "aac",
            "-ar", "48000",
            "-y",
            output_path
        ]
        
        await self.run_command(args)
    
    async def merge_audio(
        self,
        audio_files: List[str],
        output_path: str,
        bgm_file: Optional[str] = None,
        sfx_files: Optional[List[str]] = None,
        dialogue_ducking: bool = True,
        master_volume: float = 1.0
    ):
        """混合音频轨道"""
        inputs = []
        filter_complex = []
        
        # 添加对白轨道
        for i, audio in enumerate(audio_files):
            inputs.extend(["-i", audio])
            filter_complex.append(f"[{i}:a]")
        
        # 添加 BGM
        bgm_input_idx = len(audio_files)
        if bgm_file:
            inputs.extend(["-i", bgm_file])
            if dialogue_ducking and audio_files:
                # 闪避处理
                filter_complex.append(f"[{bgm_input_idx}:a]volume=0.3[a_bgm];")
            else:
                filter_complex.append(f"[{bgm_input_idx}:a]volume={master_volume}[a_bgm];")
        
        # 添加音效
        if sfx_files:
            for i, sfx in enumerate(sfx_files):
                sfx_idx = bgm_input_idx + (1 if bgm_file else 0) + i
                inputs.extend(["-i", sfx])
                filter_complex.append(f"[{sfx_idx}:a]volume={master_volume}[a_sfx{i}];")
        
        # 合并所有音频
        filter_complex.append("amix=inputs={}:duration=longest".format(
            len(audio_files) + (1 if bgm_file else 0) + (len(sfx_files) if sfx_files else 0)
        ))
        
        args = inputs + [
            "-filter_complex", "".join(filter_complex),
            "-y",
            output_path
        ]
        
        await self.run_command(args)
    
    async def add_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        font_size: int = 48,
        font_color: str = "white",
        border_color: str = "black",
        position: str = "bottom"
    ):
        """烧录字幕到视频"""
        # 根据位置计算字幕 Y 坐标
        y_position = {
            "top": "10%",
            "middle": "50%",
            "bottom": "90%"
        }.get(position, "90%")
        
        subtitle_filter = (
            f"subtitles={subtitle_path}:fontsize={font_size}:"
            f"fontcolor={font_color}:bordercolor={border_color}:"
            f"y={y_position}"
        )
        
        args = [
            "-i", video_path,
            "-vf", subtitle_filter,
            "-c:a", "copy",
            "-y",
            output_path
        ]
        
        await self.run_command(args)
    
    async def generate_srt(
        self,
        subtitles: List[Dict[str, Any]],
        output_path: str
    ):
        """生成 SRT 字幕文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitles, 1):
                start = self._format_srt_time(sub['start'])
                end = self._format_srt_time(sub['end'])
                text = sub['text']
                
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")
    
    def _format_srt_time(self, seconds: float) -> str:
        """将秒数转换为 SRT 时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    async def concat_videos(
        self,
        video_files: List[str],
        output_path: str,
        transitions: Optional[List[Dict[str, Any]]] = None
    ):
        """连接多个视频片段"""
        if not transitions:
            # 简单拼接
            concat_args = "|".join([f"file '{f}'" for f in video_files])
            
            # 创建临时文件列表
            temp_list_path = output_path + ".txt"
            with open(temp_list_path, 'w') as f:
                for video in video_files:
                    f.write(f"file '{video}'\n")
            
            args = [
                "-f", "concat",
                "-safe", "0",
                "-i", temp_list_path,
                "-c", "copy",
                "-y",
                output_path
            ]
            
            await self.run_command(args)
            
            # 清理临时文件
            Path(temp_list_path).unlink(missing_ok=True)
        else:
            # 带转场的复杂拼接（使用 xfadefilter）
            # 这里简化处理，实际需要更复杂的 filter_complex
            raise NotImplementedError("Transitions not yet implemented")
    
    async def check_availability(self) -> bool:
        """检查 FFmpeg 是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
