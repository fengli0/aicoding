import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Project, Episode, EntityProfile, ScriptScene
from adapters.llm_adapter import LLMAdapter

class NovelService:
    def __init__(self, llm_adapter: LLMAdapter):
        self.llm = llm_adapter

    async def parse_novel_text(self, text: str) -> Dict[str, Any]:
        """解析小说文本，提取章节和基础结构"""
        # 简单的章节分割规则，可优化为 LLM 辅助分割
        chapter_pattern = r"(第 [零一二三四五六七八九十百千\d]+章|第 [零一二三四五六七八九十百千\d]+节)"
        chapters = re.split(chapter_pattern, text)
        
        structured_chapters = []
        for i in range(1, len(chapters), 2):
            title = chapters[i].strip() if i < len(chapters) else "序章"
            content = chapters[i+1].strip() if i+1 < len(chapters) else ""
            structured_chapters.append({"title": title, "content": content})
            
        return {"chapters": structured_chapters, "total_length": len(text)}

    async def extract_world_building(self, text_sample: str) -> Dict[str, Any]:
        """提取世界观、人物关系和实体别名"""
        prompt = f"""
        分析以下小说片段，提取：
        1. 世界观设定 (时代、地点、核心规则)
        2. 主要人物 (姓名、身份、性格关键词)
        3. 关键实体 (重要道具、场景名称)
        4. 人物关系图谱
        
        文本片段：{text_sample[:2000]}...
        
        请以 JSON 格式返回。
        """
        result = await self.llm.generate_json(prompt)
        return result

    async def generate_episode_outlines(
        self, 
        project_id: int, 
        chapter_data: List[Dict], 
        target_episodes: int,
        db: Session
    ) -> List[Episode]:
        """生成分集大纲和核心冲突"""
        project = db.query(Project).get(project_id)
        if not project:
            raise ValueError("Project not found")

        # 合并文本供 LLM 分析整体脉络
        full_text = "\n".join([c['content'] for c in chapter_data])
        
        prompt = f"""
        基于以下小说内容，规划 {target_episodes} 集短剧大纲。
        每集时长约 3-5 分钟。
        要求：
        1. 每集必须有明确的“核心冲突”和“悬念结尾”。
        2. 输出 JSON 列表，包含：episode_number, title, summary, core_conflict, ending_hook.
        
        小说内容：{full_text[:3000]}...
        """
        
        outlines = await self.llm.generate_json(prompt)
        
        new_episodes = []
        for data in outlines.get('episodes', []):
            episode = Episode(
                project_id=project_id,
                episode_number=data.get('episode_number'),
                title=data.get('title'),
                summary=data.get('summary'),
                core_conflict=data.get('core_conflict'),
                status='draft'
            )
            db.add(episode)
            new_episodes.append(episode)
            
        db.commit()
        return new_episodes

    async def split_long_text(self, text: str, max_tokens: int = 2000) -> List[str]:
        """将长文本按语义分块，避免超出 LLM 上下文限制"""
        # 简单按段落分割，实际需结合 token 计数
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > max_tokens:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk += "\n\n" + para
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
