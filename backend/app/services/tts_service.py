# TTS (Text-to-Speech) service for dialogue and narration generation
import aiohttp
from typing import Optional, Dict, Any, List
from ..core.config import settings

class TTSService:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.TTS_SERVICE_URL
    
    async def check_connection(self) -> bool:
        """Check if TTS service is reachable"""
        if not self.base_url:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as resp:
                    return resp.status == 200
        except Exception:
            return False
    
    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices/characters"""
        if not self.base_url:
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/voices") as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("voices", [])
        except Exception:
            pass
        
        return []
    
    async def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        emotion: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0
    ) -> Dict[str, Any]:
        """Generate speech from text"""
        if not self.base_url:
            raise Exception("TTS service URL not configured")
        
        payload = {
            "text": text,
            "voice_id": voice_id,
            "speed": speed,
            "pitch": pitch,
            "volume": volume
        }
        
        if emotion:
            payload["emotion"] = emotion
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/synthesize",
                json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"TTS error: {error_text}")
                
                # Save the audio file
                content_type = resp.headers.get("Content-Type", "")
                if "audio" in content_type or resp.headers.get("Content-Disposition"):
                    with open(output_path, 'wb') as f:
                        f.write(await resp.read())
                    
                    return {
                        "status": "success",
                        "file_path": output_path,
                        "duration": self._estimate_duration(text, speed),
                        "format": "wav"
                    }
                else:
                    result = await resp.json()
                    return result
    
    def _estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """Estimate audio duration based on text length"""
        # Average Chinese characters per second: ~4-5 at normal speed
        chars = len(text.replace(" ", "").replace("\n", ""))
        base_duration = chars / 4.5  # seconds
        return base_duration / speed if speed > 0 else base_duration
    
    async def generate_with_timestamps(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate speech and return word-level timestamps for subtitles"""
        result = await self.generate_speech(
            text=text,
            voice_id=voice_id,
            output_path=output_path,
            **kwargs
        )
        
        # Generate approximate timestamps (simplified)
        words = text.split()
        total_duration = result.get("duration", 0)
        duration_per_word = total_duration / len(words) if words else 0
        
        timestamps = []
        current_time = 0.0
        for i, word in enumerate(words):
            timestamps.append({
                "word": word,
                "start": current_time,
                "end": current_time + duration_per_word
            })
            current_time += duration_per_word
        
        result["timestamps"] = timestamps
        return result
    
    async def clone_voice(
        self,
        sample_audio_path: str,
        voice_name: str
    ) -> Dict[str, Any]:
        """Clone a voice from sample audio (if supported by TTS service)"""
        if not self.base_url:
            raise Exception("TTS service URL not configured")
        
        try:
            async with aiohttp.ClientSession() as session:
                with open(sample_audio_path, 'rb') as f:
                    audio_data = f.read()
                
                form_data = aiohttp.FormData()
                form_data.add_field('audio', audio_data, filename='sample.wav')
                form_data.add_field('name', voice_name)
                
                async with session.post(
                    f"{self.base_url}/voices/clone",
                    data=form_data
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Voice cloning failed: {error_text}")
                    
                    result = await resp.json()
                    return result
        except Exception as e:
            raise Exception(f"Voice cloning not supported or failed: {str(e)}")
