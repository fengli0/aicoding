"""TTS 适配器 - 支持多种 TTS 服务"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path
import aiohttp
import asyncio


class TTSAdapter(ABC):
    """TTS 适配器基类"""
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        speed: float = 1.0,
        emotion: Optional[str] = None,
        **kwargs
    ) -> bool:
        """合成语音"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接"""
        pass


class EdgeTTSAdapter(TTSAdapter):
    """Edge TTS 适配器 (免费微软服务)"""
    
    def __init__(self):
        self.available_voices: List[Dict[str, str]] = []
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        speed: float = 1.0,
        emotion: Optional[str] = None,
        **kwargs
    ) -> bool:
        """使用 edge-tts 合成语音"""
        try:
            import edge_tts
            
            # 构建参数
            communicate = edge_tts.Communicate(text, voice_id)
            
            # 保存文件
            output_path.parent.mkdir(parents=True, exist_ok=True)
            await communicate.save(str(output_path))
            
            return True
        except Exception as e:
            print(f"Edge TTS 合成失败: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """测试 Edge TTS 连接"""
        try:
            import edge_tts
            communicate = edge_tts.Communicate("测试", "zh-CN-XiaoxiaoNeural")
            await communicate.stream()
            return True
        except Exception:
            return False
    
    async def list_voices(self, locale: str = "zh-CN") -> List[Dict[str, str]]:
        """获取可用音色列表"""
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            self.available_voices = [
                v for v in voices 
                if v.get("Locale", "").startswith(locale)
            ]
            return self.available_voices
        except Exception:
            return []


class AzureTTSAdapter(TTSAdapter):
    """Azure Cognitive Services TTS 适配器"""
    
    def __init__(self, api_key: str, region: str):
        self.api_key = api_key
        self.region = region
        self.endpoint = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        speed: float = 1.0,
        emotion: Optional[str] = None,
        **kwargs
    ) -> bool:
        """使用 Azure TTS 合成语音"""
        try:
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
            }
            
            # 构建 SSML
            rate_change = f"{int((speed - 1.0) * 100):+d}%"
            ssml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
                <voice name="{voice_id}">
                    <prosody rate="{rate_change}">{text}</prosody>
                </voice>
            </speak>"""
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    data=ssml.encode('utf-8')
                ) as response:
                    if response.status == 200:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(await response.read())
                        return True
                    else:
                        print(f"Azure TTS 错误: {response.status} - {await response.text()}")
                        return False
        except Exception as e:
            print(f"Azure TTS 合成失败: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """测试 Azure TTS 连接"""
        return await self.synthesize(
            "测试连接",
            "zh-CN-XiaoxiaoNeural",
            Path("/tmp/tts_test.mp3")
        )


class MockTTSAdapter(TTSAdapter):
    """模拟 TTS 适配器 (用于测试)"""
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        speed: float = 1.0,
        emotion: Optional[str] = None,
        **kwargs
    ) -> bool:
        """生成静音音频文件用于测试"""
        try:
            import subprocess
            
            # 计算时长 (约 15 字/秒)
            duration = max(0.5, len(text) / 15.0 / speed)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用 ffmpeg 生成静音音频
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=48000:cl=stereo:d={duration}",
                "-c:a", "aac",
                "-b:a", "128k",
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0
        except Exception as e:
            print(f"Mock TTS 失败: {e}")
            # 创建空文件作为后备
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.touch()
            return True
    
    async def test_connection(self) -> bool:
        """模拟连接测试总是成功"""
        return True


def create_tts_adapter(adapter_type: str, config: Dict[str, Any]) -> TTSAdapter:
    """工厂函数创建 TTS 适配器"""
    adapters = {
        "edge": EdgeTTSAdapter,
        "azure": lambda: AzureTTSAdapter(
            config.get("api_key", ""),
            config.get("region", "eastus")
        ),
        "mock": MockTTSAdapter,
    }
    
    adapter_class = adapters.get(adapter_type.lower(), MockTTSAdapter)
    if callable(adapter_class) and adapter_type.lower() != "mock":
        return adapter_class()
    return adapter_class()
