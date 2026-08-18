from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
import os

from core.database import get_db
from app.models import Project, Episode, ScriptScene, Shot, AssetVersion, GenerationJob
from app.schemas import (
    ProjectCreate, ProjectResponse, EpisodeCreate, EpisodeResponse,
    ScriptSceneCreate, ShotCreate, NovelImportRequest
)
from services.novel_service import NovelService
from services.script_shot_service import ScriptService, ShotService
from adapters.llm_adapter import LLMAdapter

router = APIRouter()

# 初始化服务 (实际应从依赖注入获取)
llm_adapter = LLMAdapter()  # 需配置化
novel_service = NovelService(llm_adapter)
script_service = ScriptService(llm_adapter)
shot_service = ShotService(llm_adapter)


@router.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """新建项目"""
    db_project = Project(**project.dict())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """获取项目列表"""
    projects = db.query(Project).offset(skip).limit(limit).all()
    return projects


@router.post("/projects/{project_id}/import-novel")
async def import_novel(
    project_id: int,
    request: NovelImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """导入小说并生成分集大纲"""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 解析文本
    text = request.text
    if request.file_path:
        # 从文件读取
        try:
            with open(request.file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            raise HTTPException(status_code=400, detail="Failed to read file")
    
    parsed_data = await novel_service.parse_novel_text(text)
    
    # 提取世界观和实体
    world_building = await novel_service.extract_world_building(text)
    
    # 生成分集大纲 (后台任务)
    async def generate_outlines():
        await novel_service.generate_episode_outlines(
            project_id=project_id,
            chapter_data=parsed_data['chapters'],
            target_episodes=request.target_episodes or 10,
            db=db
        )
    
    background_tasks.add_task(generate_outlines)
    
    return {
        "status": "processing",
        "chapters_count": len(parsed_data['chapters']),
        "world_building": world_building
    }


@router.post("/episodes/{episode_id}/generate-scenes")
async def generate_scenes_for_episode(
    episode_id: int,
    db: Session = Depends(get_db)
):
    """为指定分集生成剧本场次"""
    episode = db.query(Episode).get(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # 获取该项目已有实体
    entities = []  # TODO: 查询 EntityProfile
    
    scene_data = await script_service.generate_scene_details(
        episode_summary=episode.summary,
        scene_number=1,
        existing_entities=entities
    )
    
    # 创建场次记录
    new_scene = ScriptScene(
        episode_id=episode_id,
        scene_number=1,
        location=scene_data.get('scene_location'),
        time_of_day=scene_data.get('time_of_day'),
        description=scene_data.get('action_description'),
        status='draft'
    )
    db.add(new_scene)
    db.commit()
    db.refresh(new_scene)
    
    return new_scene


@router.post("/scenes/{scene_id}/generate-shots")
async def generate_shots_for_scene(
    scene_id: int,
    db: Session = Depends(get_db)
):
    """为指定场次生成分镜"""
    scene = db.query(ScriptScene).get(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # 构建场景数据结构
    scene_data = {
        "scene_location": scene.location,
        "time_of_day": scene.time_of_day,
        "action_description": scene.description,
        "dialogue": []  # TODO: 解析对白
    }
    
    shots_data = await shot_service.generate_shots_from_scene(scene_data)
    
    created_shots = []
    for shot_info in shots_data:
        shot = Shot(
            scene_id=scene_id,
            shot_number=shot_info.get('shot_number'),
            shot_type=shot_info.get('shot_type'),
            camera_movement=shot_info.get('camera_movement'),
            action=shot_info.get('action'),
            estimated_duration=shot_info.get('estimated_duration'),
            continuity_source=shot_info.get('continuity_source', 'reference_image'),
            edit_transition=shot_info.get('edit_transition', 'cut'),
            status='draft'
        )
        db.add(shot)
        created_shots.append(shot)
        
    db.commit()
    return created_shots


@router.get("/shots/{shot_id}/continuity-check")
def check_shot_continuity(shot_id: int, db: Session = Depends(get_db)):
    """检查镜头连续性依赖是否有效"""
    shot = db.query(Shot).get(shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    if shot.continuity_source == 'prev_frame':
        # 查找上一镜头
        prev_shot = db.query(Shot).filter(
            Shot.scene_id == shot.scene_id,
            Shot.shot_number == shot.shot_number - 1
        ).first()
        
        if not prev_shot:
            return {"valid": False, "reason": "No previous shot found"}
            
        # 检查上一镜头是否有已选用的视频版本
        selected_video = db.query(AssetVersion).filter(
            AssetVersion.shot_id == prev_shot.id,
            AssetVersion.is_selected == True,
            AssetVersion.media_type == 'video'
        ).first()
        
        if not selected_video:
            return {"valid": False, "reason": "Previous shot has no selected video version"}
            
        return {
            "valid": True,
            "depends_on": prev_shot.id,
            "version_id": selected_video.id
        }
    
    return {"valid": True, "reason": "Uses reference image"}
