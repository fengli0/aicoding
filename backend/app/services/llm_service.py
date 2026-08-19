# LLM service for text generation (novel parsing, prompt generation, etc.)
import aiohttp
from typing import Optional, Dict, Any, List
from ..core.config import settings

class LLMService:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.LLM_SERVICE_URL
    
    async def check_connection(self) -> bool:
        """Check if LLM service is reachable"""
        if not self.base_url:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as resp:
                    return resp.status == 200
        except Exception:
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """Generate text using LLM"""
        if not self.base_url:
            raise Exception("LLM service URL not configured")
        
        payload = {
            "prompt": prompt,
            "system_prompt": system_prompt or "You are a helpful assistant.",
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if model:
            payload["model"] = model
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/generate",
                json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"LLM error: {error_text}")
                
                result = await resp.json()
                return result.get("text", "")
    
    async def parse_novel_to_episodes(
        self,
        content: str,
        file_type: str
    ) -> Dict[str, Any]:
        """Parse novel content into episode plans and entities"""
        
        system_prompt = """你是一个专业的短剧策划专家。请分析提供的小说内容，提取以下信息：
1. 世界观设定（时代背景、地理环境、社会规则等）
2. 人物关系（主要角色、配角、他们之间的关系）
3. 实体列表（人物、地点、重要道具）
4. 分集规划（每集的标题、核心冲突、剧情概要）

请以 JSON 格式返回，包含以下结构：
{
    "world_building": {...},
    "entities": [{"name": "...", "type": "...", "description": "...", "aliases": [], "relations": {}}],
    "episodes": [{"episode_number": 1, "title": "...", "summary": "...", "core_conflict": "...", "estimated_duration": 240}]
}"""
        
        prompt = f"""请分析以下{file_type.upper()}格式的小说内容，生成分集规划和实体列表：

{content[:50000]}  # Limit to avoid token overflow

注意：
- 每集时长控制在 3-8 分钟（180-480 秒）
- 提取所有重要人物、地点和道具
- 识别人物之间的别名和关系
- 为每个实体提供详细的视觉描述以便后续生成图片"""
        
        response_text = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for structured output
        )
        
        # Parse JSON response (simplified - in production use proper JSON parsing)
        import json
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except Exception:
            pass
        
        # Fallback to basic structure
        return {
            "world_building": {"description": content[:500]},
            "entities": [],
            "episodes": []
        }
    
    async def generate_scene_prompts(
        self,
        scene_description: str,
        characters: List[Dict[str, Any]],
        location: str,
        time_of_day: str
    ) -> Dict[str, str]:
        """Generate prompts for a scene"""
        
        system_prompt = """你是一个专业的 AI 绘画提示词工程师。请根据场景描述生成详细的英文提示词，用于 Stable Diffusion 或类似模型。

要求：
- 使用英文
- 包含详细的视觉元素描述
- 包含光照、氛围、构图等信息
- 适合生成高质量的视频帧"""
        
        char_descriptions = "\n".join([
            f"- {c['name']}: {c.get('description', '')}"
            for c in characters
        ])
        
        prompt = f"""请为以下场景生成画面提示词：

场景描述：{scene_description}
地点：{location}
时间：{time_of_day}
出场人物：
{char_descriptions}

请返回以下格式的 JSON：
{{
    "positive_prompt": "...",
    "negative_prompt": "ugly, blurry, low quality, distorted, deformed, bad anatomy..."
}}"""
        
        response_text = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.5
        )
        
        import json
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except Exception:
            pass
        
        return {
            "positive_prompt": scene_description,
            "negative_prompt": "ugly, blurry, low quality, distorted"
        }
    
    async def generate_shot_list(
        self,
        scene_script: str
    ) -> List[Dict[str, Any]]:
        """Generate shot list from scene script"""
        
        system_prompt = """你是一个专业的分镜师。请根据剧本场景生成分镜列表。

每个镜头包含：
- shot_number: 镜头编号
- shot_size: 景别（extreme_long, long, medium_long, medium, medium_close, close, extreme_close）
- camera_position: 机位
- camera_movement: 运镜
- action: 动作
- estimated_duration: 预计时长（秒）
- continuity_source: 是否需要继承上一镜头（boolean）
- edit_transition: 转场类型（cut, dissolve, fade_in, fade_out）

返回 JSON 数组格式。"""
        
        prompt = f"""请为以下剧本场景生成分镜：

{scene_script}

要求：
- 每个镜头时长 2-8 秒
- 合理运用不同景别
- 考虑镜头连续性
- 标注转场方式"""
        
        response_text = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.4
        )
        
        import json
        try:
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except Exception:
            pass
        
        return []
