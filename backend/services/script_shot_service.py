from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import ScriptScene, Shot, PromptBundle
from adapters.llm_adapter import LLMAdapter

class ScriptService:
    def __init__(self, llm_adapter: LLMAdapter):
        self.llm = llm_adapter

    async def generate_scene_details(
        self, 
        episode_summary: str, 
        scene_number: int,
        existing_entities: List[Dict]
    ) -> Dict[str, Any]:
        """根据分集大纲生成具体场次细节"""
        prompt = f"""
        基于分集大纲：{episode_summary}
        生成第 {scene_number} 场的详细剧本要素。
        
        已知实体信息：{existing_entities}
        
        请返回 JSON 格式，包含：
        - scene_location (地点)
        - time_of_day (时间/昼夜)
        - characters (出场人物列表)
        - costumes (服装造型描述)
        - props (关键道具)
        - action_description (动作描述)
        - dialogue (对白列表，含角色和台词)
        - narration (旁白内容)
        - audio_requirements (音频需求：BGM 类型、音效)
        """
        return await self.llm.generate_json(prompt)

    async def convert_to_script_format(self, scene_data: Dict) -> str:
        """将结构化数据转换为标准剧本格式文本"""
        lines = []
        lines.append(f"场景：{scene_data.get('scene_location', '未知')}")
        lines.append(f"时间：{scene_data.get('time_of_day', '日')}")
        lines.append("")
        
        if scene_data.get('characters'):
            lines.append(f"人物：{', '.join(scene_data['characters'])}")
            lines.append("")
            
        if scene_data.get('action_description'):
            lines.append(f"[动作] {scene_data['action_description']}")
            lines.append("")
            
        for line in scene_data.get('dialogue', []):
            char = line.get('character', '未知')
            text = line.get('text', '')
            lines.append(f"{char}: {text}")
            
        if scene_data.get('narration'):
            lines.append("")
            lines.append(f"(旁白：{scene_data['narration']})")
            
        return "\n".join(lines)


class ShotService:
    def __init__(self, llm_adapter: LLMAdapter):
        self.llm = llm_adapter

    async def generate_shots_from_scene(
        self, 
        scene_data: Dict, 
        prev_shot_end_state: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """根据场次数据生成分镜列表"""
        prompt = f"""
        基于以下场景信息生成分镜列表：
        地点：{scene_data.get('scene_location')}
        动作：{scene_data.get('action_description')}
        对白：{scene_data.get('dialogue')}
        
        上一镜头结束状态 (如有): {prev_shot_end_state}
        
        要求：
        1. 每个镜头包含：shot_number, shot_type (景别), camera_movement (运镜), action, estimated_duration.
        2. 考虑镜头连续性：如果动作连续，标记 continuity_source='prev_frame'。
        3. 明确转场方式 (edit_transition): cut, dissolve, fade_in, fade_out.
        4. 预计总时长覆盖对白时长。
        
        返回 JSON 列表。
        """
        shots_data = await self.llm.generate_json(prompt)
        return shots_data.get('shots', [])

    def analyze_continuity(
        self, 
        current_shot: Dict, 
        prev_shot: Dict, 
        scene_context: Dict
    ) -> Dict[str, Any]:
        """自动分析镜头连续性规则"""
        # 确定性规则优先
        if current_shot.get('scene_location') != prev_shot.get('scene_location'):
            return {"continuity_source": "reference_image", "reason": "场景切换"}
            
        if current_shot.get('time_of_day') != prev_shot.get('time_of_day'):
            return {"continuity_source": "reference_image", "reason": "时间跳跃"}
            
        if current_shot.get('edit_transition') == 'cut':
            # 硬切通常不继承，除非是极短的动作衔接
            return {"continuity_source": "reference_image", "reason": "硬切转场"}
            
        # 默认连续动作继承上一帧
        return {"continuity_source": "prev_frame", "reason": "连续动作"}

    async def suggest_prompt_for_shot(
        self, 
        shot_data: Dict, 
        entity_prompts: Dict[str, str],
        scene_prompts: Dict[str, str]
    ) -> str:
        """组合实体和场景提示词，生成镜头专用提示词"""
        base_prompt_parts = []
        
        # 添加场景描述
        scene_id = shot_data.get('scene_id')
        if scene_id and scene_id in scene_prompts:
            base_prompt_parts.append(scene_prompts[scene_id])
            
        # 添加人物及造型
        for entity_id in shot_data.get('entities', []):
            if entity_id in entity_prompts:
                base_prompt_parts.append(entity_prompts[entity_id])
                
        # 添加镜头特有动作和运镜
        base_prompt_parts.append(f"动作：{shot_data.get('action')}")
        base_prompt_parts.append(f"景别：{shot_data.get('shot_type')}")
        base_prompt_parts.append(f"运镜：{shot_data.get('camera_movement')}")
        
        combined_prompt = ", ".join(base_prompt_parts)
        
        # 可选：用 LLM 润色提示词
        # refine_prompt = f"优化以下视频生成提示词，使其更具画面感：{combined_prompt}"
        # return await self.llm.generate_text(refine_prompt)
        
        return combined_prompt
