"""
FastAPI 主应用
提供本地 REST API 管理项目、剧本、分镜、素材、版本和导出任务
通过 WebSocket 推送队列进度、预览结果和错误
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from backend.core.database import Database
from backend.core.task_queue import TaskQueue
from backend.adapters.model_adapters import create_adapter, ModelConfig
from backend.services.ffmpeg_service import FFmpegService


# 创建 FastAPI 应用
app = FastAPI(
    title="AI 短剧生成工作台",
    description="单机本地 Web 应用，采用阶段式工作流生成中文横屏短剧",
    version="0.1.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局状态
db: Optional[Database] = None
task_queue: Optional[TaskQueue] = None
ffmpeg_service: Optional[FFmpegService] = None
adapters: Dict[str, Any] = {}
websocket_clients: List[WebSocket] = []


class AppSettings(BaseModel):
    """应用设置"""
    llm_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    image_url: str = ""
    image_model: str = ""
    video_url: str = ""
    video_model: str = "minimax-h3"
    tts_url: str = ""
    tts_api_key: str = ""
    tts_voice: str = ""
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    project_root: str = "./projects"


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global db, task_queue, ffmpeg_service
    
    # 初始化数据库
    db = Database("./aicoding.db")
    
    # 初始化任务队列
    task_queue = TaskQueue(db)
    
    # 注册任务处理器
    task_queue.register_handler("llm", handle_llm_job)
    task_queue.register_handler("image", handle_image_job)
    task_queue.register_handler("video", handle_video_job)
    task_queue.register_handler("tts", handle_tts_job)
    
    # 启动后台工作线程
    await task_queue.start_worker()
    
    # 初始化 FFmpeg 服务
    ffmpeg_service = FFmpegService()
    
    # 检查 FFmpeg 可用性
    if not await ffmpeg_service.check_availability():
        print("Warning: FFmpeg not found or not working")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    if task_queue:
        await task_queue.stop_worker()


async def handle_llm_job(job_data: Dict) -> Dict:
    """处理 LLM 任务"""
    adapter = adapters.get("llm")
    if not adapter:
        raise RuntimeError("LLM adapter not configured")
    
    params = json.loads(job_data.get("parameters", "{}"))
    result = await adapter.generate(
        prompt=params.get("prompt", ""),
        system_prompt=params.get("system_prompt"),
        **params.get("extra", {})
    )
    
    if not result.success:
        raise RuntimeError(result.error_message)
    
    return {"text": result.data}


async def handle_image_job(job_data: Dict) -> Dict:
    """处理图片生成任务"""
    adapter = adapters.get("image")
    if not adapter:
        raise RuntimeError("Image adapter not configured")
    
    params = json.loads(job_data.get("parameters", "{}"))
    result = await adapter.generate(
        prompt=params.get("prompt", ""),
        negative_prompt=params.get("negative_prompt", ""),
        width=params.get("width", 1920),
        height=params.get("height", 1080),
        seed=params.get("seed"),
        reference_images=params.get("reference_images"),
        **params.get("extra", {})
    )
    
    if not result.success:
        raise RuntimeError(result.error_message)
    
    return result.data


async def handle_video_job(job_data: Dict) -> Dict:
    """处理视频生成任务"""
    adapter = adapters.get("video")
    if not adapter:
        raise RuntimeError("Video adapter not configured")
    
    params = json.loads(job_data.get("parameters", "{}"))
    result = await adapter.generate(
        prompt=params.get("prompt", ""),
        reference_images=params.get("reference_images"),
        duration=params.get("duration", 5.0),
        width=params.get("width", 1920),
        height=params.get("height", 1080),
        fps=params.get("fps", 25),
        seed=params.get("seed"),
        continuity_frame=params.get("continuity_frame"),
        **params.get("extra", {})
    )
    
    if not result.success:
        raise RuntimeError(result.error_message)
    
    return result.data


async def handle_tts_job(job_data: Dict) -> Dict:
    """处理 TTS 任务"""
    adapter = adapters.get("tts")
    if not adapter:
        raise RuntimeError("TTS adapter not configured")
    
    params = json.loads(job_data.get("parameters", "{}"))
    result = await adapter.generate(
        text=params.get("text", ""),
        voice_id=params.get("voice_id", ""),
        emotion=params.get("emotion", "neutral"),
        speed=params.get("speed", 1.0),
        **params.get("extra", {})
    )
    
    if not result.success:
        raise RuntimeError(result.error_message)
    
    return {"audio_data": result.data}


# WebSocket 连接管理
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接用于推送任务进度和错误"""
    await websocket.accept()
    websocket_clients.append(websocket)
    
    try:
        while True:
            # 保持连接
            data = await websocket.receive_text()
            
            # 可以处理客户端消息
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)


async def broadcast_message(message: Dict):
    """向所有 WebSocket 客户端广播消息"""
    for client in websocket_clients:
        try:
            await client.send_json(message)
        except Exception:
            pass


# ==================== 项目 API ====================

@app.get("/api/projects")
async def list_projects():
    """获取项目列表"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects ORDER BY updated_at DESC')
        projects = [dict(row) for row in cursor.fetchall()]
    
    # 解析 JSON 字段
    for project in projects:
        project['settings'] = json.loads(project.get('settings', '{}'))
    
    return {"projects": projects}


@app.post("/api/projects")
async def create_project(project_data: Dict):
    """创建新项目"""
    project_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (
                id, name, description, created_at, updated_at, status, settings
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            project_id,
            project_data.get('name', 'Untitled Project'),
            project_data.get('description', ''),
            now,
            now,
            'draft',
            json.dumps(project_data.get('settings', {}))
        ))
    
    return {"id": project_id, "message": "Project created"}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """获取项目详情"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = dict(row)
        project['settings'] = json.loads(project.get('settings', '{}'))
        
        return project


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    
    return {"message": "Project deleted"}


# ==================== 分集 API ====================

@app.get("/api/projects/{project_id}/episodes")
async def list_episodes(project_id: str):
    """获取项目的分集列表"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM episodes WHERE project_id = ? ORDER BY episode_number',
            (project_id,)
        )
        episodes = [dict(row) for row in cursor.fetchall()]
    
    return {"episodes": episodes}


@app.post("/api/projects/{project_id}/episodes")
async def create_episode(project_id: str, episode_data: Dict):
    """创建新分集"""
    episode_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO episodes (
                id, project_id, episode_number, title, summary,
                created_at, updated_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            episode_id,
            project_id,
            episode_data.get('episode_number', 1),
            episode_data.get('title', ''),
            episode_data.get('summary', ''),
            now,
            now,
            'draft'
        ))
    
    return {"id": episode_id, "message": "Episode created"}


# ==================== 设置 API ====================

@app.get("/api/settings")
async def get_settings():
    """获取当前设置"""
    return {
        "llm": {
            "url": adapters.get("llm", {}).config.service_url if "llm" in adapters else "",
            "model": adapters.get("llm", {}).config.model_name if "llm" in adapters else ""
        },
        "image": {
            "url": adapters.get("image", {}).config.service_url if "image" in adapters else "",
            "model": adapters.get("image", {}).config.model_name if "image" in adapters else ""
        },
        "video": {
            "url": adapters.get("video", {}).config.service_url if "video" in adapters else "",
            "model": adapters.get("video", {}).config.model_name if "video" in adapters else ""
        },
        "tts": {
            "url": adapters.get("tts", {}).config.service_url if "tts" in adapters else "",
            "voice": adapters.get("tts", {}).config.model_name if "tts" in adapters else ""
        },
        "ffmpeg": ffmpeg_service.ffmpeg_path if ffmpeg_service else "ffmpeg"
    }


@app.post("/api/settings")
async def update_settings(settings: AppSettings):
    """更新设置"""
    global adapters
    
    # 重新初始化适配器
    adapters = {}
    
    if settings.llm_url:
        adapters["llm"] = create_adapter("llm", ModelConfig(
            service_url=settings.llm_url,
            api_key=settings.llm_api_key,
            model_name=settings.llm_model
        ))
    
    if settings.image_url:
        adapters["image"] = create_adapter("image", ModelConfig(
            service_url=settings.image_url,
            model_name=settings.image_model
        ))
    
    if settings.video_url:
        adapters["video"] = create_adapter("video", ModelConfig(
            service_url=settings.video_url,
            model_name=settings.video_model
        ))
    
    if settings.tts_url:
        adapters["tts"] = create_adapter("tts", ModelConfig(
            service_url=settings.tts_url,
            api_key=settings.tts_api_key,
            model_name=settings.tts_voice
        ))
    
    return {"message": "Settings updated"}


@app.post("/api/settings/test/{adapter_type}")
async def test_adapter_connection(adapter_type: str):
    """测试适配器连接"""
    adapter = adapters.get(adapter_type)
    
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Adapter {adapter_type} not configured")
    
    success = await adapter.test_connection()
    
    return {"success": success, "adapter": adapter_type}


# ==================== 任务队列 API ====================

@app.get("/api/jobs")
async def list_jobs(project_id: Optional[str] = None):
    """获取任务列表"""
    jobs = task_queue.get_pending_jobs(project_id)
    return {"jobs": jobs}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """取消任务"""
    await task_queue.cancel_job(job_id)
    return {"message": "Job cancelled"}


# ==================== 健康检查 ====================

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "database": True if db else False,
        "task_queue": True if task_queue else False,
        "ffmpeg": await ffmpeg_service.check_availability() if ffmpeg_service else False
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
