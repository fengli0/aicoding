"""后端 API 路由 - 完整实现"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import shutil

router = APIRouter()

# ==================== Pydantic 模型 ====================

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    resolution_width: int = 1920
    resolution_height: int = 1080
    fps: int = 25
    target_duration_min: int = 3
    target_duration_max: int = 8

class EpisodeCreate(BaseModel):
    project_id: str
    episode_number: int
    title: str
    summary: str = ""
    core_conflict: str = ""

class ScriptSceneCreate(BaseModel):
    episode_id: str
    scene_number: int
    location: str
    time_of_day: str
    interior_exterior: str
    characters: List[str] = []
    costumes: Dict[str, str] = {}
    props: List[str] = []
    actions: str
    dialogues: List[Dict[str, Any]] = []
    narration: str = ""
    audio_requirements: List[str] = []

class ShotCreate(BaseModel):
    scene_id: str
    shot_number: int
    shot_size: str
    camera_position: str = ""
    camera_movement: str = ""
    action: str
    dialogue: str = ""
    narration: str = ""
    estimated_duration: float
    frame_start_state: str = ""
    frame_end_state: str = ""
    continuity_source: str = "reference_image"
    edit_transition: str = "cut"
    transition_duration: float = 0.0
    characters: List[str] = []
    scene_ref: str = ""
    prop_refs: List[str] = []

class PromptBundleCreate(BaseModel):
    project_id: str
    type: str
    entity_id: Optional[str] = None
    positive_prompt: str
    negative_prompt: str = ""
    model_params: Dict[str, Any] = {}
    seed: Optional[int] = None
    locked: bool = False

class EntityProfileCreate(BaseModel):
    project_id: str
    name: str
    type: str
    description: str
    aliases: List[str] = []
    metadata: Dict[str, Any] = {}

class TTSRequest(BaseModel):
    text: str
    voice_id: str
    speed: float = 1.0
    emotion: Optional[str] = None
    output_path: str

class VideoGenerateRequest(BaseModel):
    shot_id: str
    prompt: str
    negative_prompt: str = ""
    reference_image_path: Optional[str] = None
    continuity_frame_path: Optional[str] = None
    width: int = 1920
    height: int = 1080
    duration: float = 3.0
    fps: int = 25
    seed: Optional[int] = None
    steps: int = 30
    cfg_scale: float = 7.0

class ExportRequest(BaseModel):
    project_id: str
    episode_id: Optional[str] = None
    format: str = "mp4"
    include_subtitles: bool = True
    output_resolution: Dict[str, int] = {"width": 1920, "height": 1080}
    output_fps: int = 25


# ==================== 辅助函数 ====================

def get_db():
    db = sqlite3.connect('data/dramacraft.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """初始化数据库表"""
    db = get_db()
    cursor = db.cursor()
    
    # 项目表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft',
            resolution_width INTEGER DEFAULT 1920,
            resolution_height INTEGER DEFAULT 1080,
            aspect_ratio TEXT DEFAULT '16:9',
            fps INTEGER DEFAULT 25,
            target_duration_min INTEGER DEFAULT 3,
            target_duration_max INTEGER DEFAULT 8
        )
    ''')
    
    # 分集表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS episodes (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            episode_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            core_conflict TEXT,
            status TEXT DEFAULT 'draft',
            script_status TEXT DEFAULT 'draft',
            storyboard_status TEXT DEFAULT 'draft',
            asset_status TEXT DEFAULT 'draft',
            video_status TEXT DEFAULT 'draft',
            audio_status TEXT DEFAULT 'draft',
            composite_status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # 剧本场景表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS script_scenes (
            id TEXT PRIMARY KEY,
            episode_id TEXT NOT NULL,
            scene_number INTEGER NOT NULL,
            location TEXT,
            time_of_day TEXT,
            interior_exterior TEXT,
            characters TEXT,
            costumes TEXT,
            props TEXT,
            actions TEXT,
            dialogues TEXT,
            narration TEXT,
            audio_requirements TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (episode_id) REFERENCES episodes(id)
        )
    ''')
    
    # 分镜表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shots (
            id TEXT PRIMARY KEY,
            scene_id TEXT NOT NULL,
            shot_number INTEGER NOT NULL,
            shot_size TEXT,
            camera_position TEXT,
            camera_movement TEXT,
            action TEXT,
            dialogue TEXT,
            narration TEXT,
            estimated_duration REAL,
            frame_start_state TEXT,
            frame_end_state TEXT,
            continuity_source TEXT,
            continuity_ref_shot_id TEXT,
            edit_transition TEXT,
            transition_duration REAL,
            characters TEXT,
            scene_ref TEXT,
            prop_refs TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scene_id) REFERENCES script_scenes(id)
        )
    ''')
    
    # 素材版本表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asset_versions (
            id TEXT PRIMARY KEY,
            asset_type TEXT NOT NULL,
            entity_id TEXT,
            shot_id TEXT,
            version_number INTEGER NOT NULL,
            file_path TEXT,
            thumbnail_path TEXT,
            model_name TEXT,
            workflow_version TEXT,
            parameters TEXT,
            seed INTEGER,
            input_assets TEXT,
            dependency_versions TEXT,
            status TEXT DEFAULT 'draft',
            error_message TEXT,
            width INTEGER,
            height INTEGER,
            duration REAL,
            fps REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_current INTEGER DEFAULT 1,
            FOREIGN KEY (shot_id) REFERENCES shots(id)
        )
    ''')
    
    # 生成任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generation_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            project_id TEXT NOT NULL,
            episode_id TEXT,
            shot_id TEXT,
            asset_id TEXT,
            parameters TEXT,
            workflow_json TEXT,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 2,
            comfyui_job_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            completed_at TEXT
        )
    ''')
    
    # 提示词包表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompt_bundles (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            type TEXT NOT NULL,
            entity_id TEXT,
            positive_prompt TEXT,
            negative_prompt TEXT,
            model_params TEXT,
            seed INTEGER,
            locked INTEGER DEFAULT 0,
            current_version_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # 实体档案表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entity_profiles (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            aliases TEXT,
            image_url TEXT,
            prompt_bundle_id TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    db.commit()
    db.close()

# 初始化数据库
init_db()


# ==================== 项目路由 ====================

@router.get("/projects")
async def list_projects():
    """获取所有项目列表"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    db.close()
    return [dict(row) for row in rows]

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """获取项目详情"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")
    return dict(row)

@router.post("/projects")
async def create_project(project: ProjectCreate):
    """创建新项目"""
    db = get_db()
    cursor = db.cursor()
    
    project_id = f"proj_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    cursor.execute('''
        INSERT INTO projects (id, name, description, resolution_width, resolution_height, fps, target_duration_min, target_duration_max)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (project_id, project.name, project.description, 
          project.resolution_width, project.resolution_height, project.fps,
          project.target_duration_min, project.target_duration_max))
    
    db.commit()
    db.close()
    
    return {"id": project_id, "name": project.name, "status": "created"}

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    db.close()
    return {"status": "deleted"}


# ==================== 分集路由 ====================

@router.get("/episodes")
async def list_episodes(project_id: Optional[str] = None):
    """获取分集列表"""
    db = get_db()
    cursor = db.cursor()
    if project_id:
        cursor.execute("SELECT * FROM episodes WHERE project_id = ? ORDER BY episode_number", (project_id,))
    else:
        cursor.execute("SELECT * FROM episodes ORDER BY episode_number")
    rows = cursor.fetchall()
    db.close()
    return [dict(row) for row in rows]

@router.post("/episodes")
async def create_episode(episode: EpisodeCreate):
    """创建分集"""
    db = get_db()
    cursor = db.cursor()
    
    episode_id = f"ep_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO episodes (id, project_id, episode_number, title, summary, core_conflict)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (episode_id, episode.project_id, episode.episode_number, 
          episode.title, episode.summary, episode.core_conflict))
    
    db.commit()
    db.close()
    
    return {"id": episode_id, "episode_number": episode.episode_number, "title": episode.title}


# ==================== 剧本路由 ====================

@router.get("/script-scenes")
async def list_script_scenes(episode_id: str):
    """获取剧本场景列表"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM script_scenes WHERE episode_id = ? ORDER BY scene_number", (episode_id,))
    rows = cursor.fetchall()
    db.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['characters'] = json.loads(d['characters'] or '[]')
        d['costumes'] = json.loads(d['costumes'] or '{}')
        d['props'] = json.loads(d['props'] or '[]')
        d['dialogues'] = json.loads(d['dialogues'] or '[]')
        d['audio_requirements'] = json.loads(d['audio_requirements'] or '[]')
        result.append(d)
    
    return result

@router.post("/script-scenes")
async def create_script_scene(scene: ScriptSceneCreate):
    """创建剧本场景"""
    db = get_db()
    cursor = db.cursor()
    
    scene_id = f"scene_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO script_scenes (id, episode_id, scene_number, location, time_of_day, 
            interior_exterior, characters, costumes, props, actions, dialogues, 
            narration, audio_requirements)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (scene_id, scene.episode_id, scene.scene_number, scene.location,
          scene.time_of_day, scene.interior_exterior, json.dumps(scene.characters),
          json.dumps(scene.costumes), json.dumps(scene.props), scene.actions,
          json.dumps(scene.dialogues), scene.narration, json.dumps(scene.audio_requirements)))
    
    db.commit()
    db.close()
    
    return {"id": scene_id, "scene_number": scene.scene_number, "location": scene.location}


# ==================== 分镜路由 ====================

@router.get("/shots")
async def list_shots(scene_id: Optional[str] = None, episode_id: Optional[str] = None):
    """获取分镜列表"""
    db = get_db()
    cursor = db.cursor()
    
    if scene_id:
        cursor.execute("SELECT * FROM shots WHERE scene_id = ? ORDER BY shot_number", (scene_id,))
    elif episode_id:
        cursor.execute('''
            SELECT s.* FROM shots s
            JOIN script_scenes sc ON s.scene_id = sc.id
            WHERE sc.episode_id = ? ORDER BY sc.scene_number, s.shot_number
        ''', (episode_id,))
    else:
        cursor.execute("SELECT * FROM shots ORDER BY shot_number")
    
    rows = cursor.fetchall()
    db.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['characters'] = json.loads(d['characters'] or '[]')
        d['prop_refs'] = json.loads(d['prop_refs'] or '[]')
        result.append(d)
    
    return result

@router.post("/shots")
async def create_shot(shot: ShotCreate):
    """创建分镜"""
    db = get_db()
    cursor = db.cursor()
    
    shot_id = f"shot_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO shots (id, scene_id, shot_number, shot_size, camera_position,
            camera_movement, action, dialogue, narration, estimated_duration,
            frame_start_state, frame_end_state, continuity_source, edit_transition,
            transition_duration, characters, scene_ref, prop_refs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (shot_id, shot.scene_id, shot.shot_number, shot.shot_size,
          shot.camera_position, shot.camera_movement, shot.action, shot.dialogue,
          shot.narration, shot.estimated_duration, shot.frame_start_state,
          shot.frame_end_state, shot.continuity_source, shot.edit_transition,
          shot.transition_duration, json.dumps(shot.characters), shot.scene_ref,
          json.dumps(shot.prop_refs)))
    
    db.commit()
    db.close()
    
    return {"id": shot_id, "shot_number": shot.shot_number, "shot_size": shot.shot_size}


# ==================== 提示词路由 ====================

@router.get("/prompt-bundles")
async def list_prompt_bundles(project_id: Optional[str] = None):
    """获取提示词包列表"""
    db = get_db()
    cursor = db.cursor()
    if project_id:
        cursor.execute("SELECT * FROM prompt_bundles WHERE project_id = ?", (project_id,))
    else:
        cursor.execute("SELECT * FROM prompt_bundles")
    rows = cursor.fetchall()
    db.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['model_params'] = json.loads(d['model_params'] or '{}')
        d['locked'] = bool(d['locked'])
        result.append(d)
    
    return result

@router.post("/prompt-bundles")
async def create_prompt_bundle(bundle: PromptBundleCreate):
    """创建提示词包"""
    db = get_db()
    cursor = db.cursor()
    
    bundle_id = f"prompt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO prompt_bundles (id, project_id, type, entity_id, positive_prompt,
            negative_prompt, model_params, seed, locked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (bundle_id, bundle.project_id, bundle.type, bundle.entity_id,
          bundle.positive_prompt, bundle.negative_prompt,
          json.dumps(bundle.model_params), bundle.seed, 1 if bundle.locked else 0))
    
    db.commit()
    db.close()
    
    return {"id": bundle_id, "type": bundle.type}


# ==================== 实体路由 ====================

@router.get("/entity-profiles")
async def list_entities(project_id: Optional[str] = None, entity_type: Optional[str] = None):
    """获取实体档案列表"""
    db = get_db()
    cursor = db.cursor()
    
    if project_id and entity_type:
        cursor.execute("SELECT * FROM entity_profiles WHERE project_id = ? AND type = ?", (project_id, entity_type))
    elif project_id:
        cursor.execute("SELECT * FROM entity_profiles WHERE project_id = ?", (project_id,))
    else:
        cursor.execute("SELECT * FROM entity_profiles")
    
    rows = cursor.fetchall()
    db.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['aliases'] = json.loads(d['aliases'] or '[]')
        d['metadata'] = json.loads(d['metadata'] or '{}')
        result.append(d)
    
    return result

@router.post("/entity-profiles")
async def create_entity(entity: EntityProfileCreate):
    """创建实体档案"""
    db = get_db()
    cursor = db.cursor()
    
    entity_id = f"entity_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO entity_profiles (id, project_id, name, type, description, aliases, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (entity_id, entity.project_id, entity.name, entity.type,
          entity.description, json.dumps(entity.aliases), json.dumps(entity.metadata)))
    
    db.commit()
    db.close()
    
    return {"id": entity_id, "name": entity.name, "type": entity.type}


# ==================== 视频生成路由 ====================

@router.post("/video/generate")
async def generate_video(request: VideoGenerateRequest, background_tasks: BackgroundTasks):
    """提交视频生成任务"""
    from app.services.comfyui_service import ComfyUIService
    
    db = get_db()
    cursor = db.cursor()
    
    job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO generation_jobs (id, job_type, project_id, shot_id, parameters, status)
        VALUES (?, 'video', ?, ?, ?, 'pending')
    ''', (job_id, request.shot_id.split('_')[0], request.shot_id, json.dumps(request.dict())))
    
    db.commit()
    db.close()
    
    # 后台执行生成任务
    async def run_generation():
        service = ComfyUIService()
        try:
            await service.generate_video(job_id, request.dict())
        except Exception as e:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                UPDATE generation_jobs SET status = 'failed', error_message = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (str(e), job_id))
            db.commit()
            db.close()
    
    background_tasks.add_task(run_generation)
    
    return {"job_id": job_id, "status": "pending"}


# ==================== TTS 路由 ====================

@router.post("/tts/synthesize")
async def synthesize_tts(request: TTSRequest, background_tasks: BackgroundTasks):
    """合成语音"""
    from app.adapters.tts_adapter import create_tts_adapter
    
    job_id = f"tts_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    async def run_tts():
        adapter = create_tts_adapter("mock", {})
        from pathlib import Path
        success = await adapter.synthesize(
            text=request.text,
            voice_id=request.voice_id,
            output_path=Path(request.output_path),
            speed=request.speed,
            emotion=request.emotion
        )
        print(f"TTS 任务 {job_id} 完成：{success}")
    
    background_tasks.add_task(run_tts)
    
    return {"job_id": job_id, "status": "pending"}


# ==================== 导出路由 ====================

@router.post("/export")
async def create_export_job(request: ExportRequest, background_tasks: BackgroundTasks):
    """创建导出任务"""
    db = get_db()
    cursor = db.cursor()
    
    job_id = f"export_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor.execute('''
        INSERT INTO generation_jobs (id, job_type, project_id, episode_id, parameters, status)
        VALUES (?, 'export', ?, ?, ?, 'pending')
    ''', (job_id, request.project_id, request.episode_id, json.dumps(request.dict())))
    
    db.commit()
    db.close()
    
    return {"job_id": job_id, "status": "pending"}


# ==================== 任务队列路由 ====================

@router.get("/jobs")
async def list_jobs(status: Optional[str] = None, job_type: Optional[str] = None):
    """获取任务列表"""
    db = get_db()
    cursor = db.cursor()
    
    query = "SELECT * FROM generation_jobs"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    if job_type:
        query += " AND job_type = ?" if status else " WHERE job_type = ?"
        params.append(job_type)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    db.close()
    
    result = []
    for row in rows:
        d = dict(row)
        d['parameters'] = json.loads(d['parameters'] or '{}')
        result.append(d)
    
    return result

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """获取任务详情"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    d = dict(row)
    d['parameters'] = json.loads(d['parameters'] or '{}')
    return d


# ==================== WebSocket 路由 ====================

@router.websocket("/ws/jobs")
async def websocket_jobs(websocket: WebSocket):
    """WebSocket 推送任务进度"""
    await websocket.accept()
    try:
        while True:
            # 保持连接，定期发送心跳
            await websocket.send_json({"type": "heartbeat", "timestamp": datetime.now().isoformat()})
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        print("WebSocket 客户端断开连接")
    except Exception as e:
        print(f"WebSocket 错误：{e}")


# ==================== 设置路由 ====================

@router.get("/settings")
async def get_settings():
    """获取应用设置"""
    return {
        "comfyui": {
            "enabled": True,
            "base_url": "http://127.0.0.1:8188",
            "workflow_path": "workflows/minimax_h3_video.json",
            "timeout": 300,
            "max_retries": 2
        },
        "tts": {
            "provider": "mock",
            "default_voice": "zh-CN-XiaoxiaoNeural",
            "default_speed": 1.0
        },
        "llm": {
            "provider": "local",
            "model": "qwen2.5:7b",
            "max_tokens": 4096,
            "temperature": 0.7
        },
        "output": {
            "resolution": {"width": 1920, "height": 1080},
            "fps": 25,
            "format": "mp4",
            "codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000
        }
    }
