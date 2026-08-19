# API routes for projects, episodes, scripts, shots, assets, jobs, etc.
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import os

from ..db.database import get_db
from ..models.schemas import (
    Project, Episode, EntityProfile, ScriptScene, Shot,
    PromptBundle, AssetVersion, GenerationJob, StageStatus, ExportJob, TimelineClip
)
from ..models.schemas_api import (
    ProjectCreate, ProjectResponse,
    EpisodeCreate, EpisodeResponse,
    EntityProfileCreate, EntityProfileResponse,
    ScriptSceneCreate, ScriptSceneResponse,
    ShotCreate, ShotResponse,
    PromptBundleCreate, PromptBundleResponse,
    AssetVersionResponse, GenerationJobResponse,
    NovelImportRequest, NovelImportResponse
)
from ..services.task_queue import task_queue
from ..services.llm_service import LLMService
from ..services.tts_service import TTSService
from ..services.ffmpeg_service import FFmpegService
from ..services.comfyui_service import ComfyUIService
from ..services.continuity_service import ContinuityService
from ..core.config import settings

router = APIRouter()

# Project endpoints
@router.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(name=project.name, description=project.description)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    projects = db.query(Project).offset(skip).limit(limit).all()
    return projects

@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "deleted"}

# Episode endpoints
@router.post("/episodes", response_model=EpisodeResponse)
def create_episode(episode: EpisodeCreate, db: Session = Depends(get_db)):
    db_episode = Episode(**episode.dict())
    db.add(db_episode)
    db.commit()
    db.refresh(db_episode)
    return db_episode

@router.get("/projects/{project_id}/episodes", response_model=List[EpisodeResponse])
def list_episodes(project_id: int, db: Session = Depends(get_db)):
    episodes = db.query(Episode).filter(Episode.project_id == project_id).order_by(Episode.episode_number).all()
    return episodes

@router.get("/episodes/{episode_id}", response_model=EpisodeResponse)
def get_episode(episode_id: int, db: Session = Depends(get_db)):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode

# Novel import endpoint
@router.post("/novel/import", response_model=NovelImportResponse)
async def import_novel(request: NovelImportRequest, db: Session = Depends(get_db)):
    content = request.content
    if not content and request.file_path:
        try:
            with open(request.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            raise HTTPException(status_code=400, detail="Failed to read file")
    
    if not content:
        raise HTTPException(status_code=400, detail="No content provided")
    
    llm = LLMService()
    result = await llm.parse_novel_to_episodes(content, request.file_type)
    
    # Create entities in database
    entities = []
    for entity_data in result.get("entities", []):
        entity = EntityProfile(
            project_id=request.project_id,
            name=entity_data["name"],
            entity_type=entity_data.get("type", "character"),
            description=entity_data.get("description", ""),
            aliases=entity_data.get("aliases", []),
            relations=entity_data.get("relations", {}),
            world_building=result.get("world_building", {})
        )
        db.add(entity)
        entities.append(entity)
    
    db.commit()
    
    # Convert to response format
    entity_responses = [
        EntityProfileResponse(
            id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            description=e.description,
            aliases=e.aliases or [],
            relations=e.relations or {},
            world_building=e.world_building or {}
        )
        for e in entities
    ]
    
    return NovelImportResponse(
        entities=entity_responses,
        episodes=result.get("episodes", []),
        world_building=result.get("world_building", {})
    )

# Scene endpoints
@router.post("/scenes", response_model=ScriptSceneResponse)
def create_scene(scene: ScriptSceneCreate, db: Session = Depends(get_db)):
    db_scene = ScriptScene(**scene.dict())
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    return db_scene

@router.get("/episodes/{episode_id}/scenes", response_model=List[ScriptSceneResponse])
def list_scenes(episode_id: int, db: Session = Depends(get_db)):
    scenes = db.query(ScriptScene).filter(ScriptScene.episode_id == episode_id).order_by(ScriptScene.scene_number).all()
    return scenes

@router.put("/scenes/{scene_id}", response_model=ScriptSceneResponse)
def update_scene(scene_id: int, scene_data: dict, db: Session = Depends(get_db)):
    scene = db.query(ScriptScene).filter(ScriptScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    for key, value in scene_data.items():
        setattr(scene, key, value)
    
    db.commit()
    db.refresh(scene)
    return scene

# Shot endpoints
@router.post("/shots", response_model=ShotResponse)
def create_shot(shot: ShotCreate, db: Session = Depends(get_db)):
    db_shot = Shot(**shot.dict())
    db.add(db_shot)
    db.commit()
    db.refresh(db_shot)
    return db_shot

@router.get("/scenes/{scene_id}/shots", response_model=List[ShotResponse])
def list_shots(scene_id: int, db: Session = Depends(get_db)):
    shots = db.query(Shot).filter(Shot.scene_id == scene_id).order_by(Shot.shot_number).all()
    return shots

@router.put("/shots/{shot_id}", response_model=ShotResponse)
def update_shot(shot_id: int, shot_data: dict, db: Session = Depends(get_db)):
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    for key, value in shot_data.items():
        setattr(shot, key, value)
    
    db.commit()
    db.refresh(shot)
    return shot

# Generate shots from scene using LLM
@router.post("/scenes/{scene_id}/generate-shots", response_model=List[ShotResponse])
async def generate_shots_for_scene(scene_id: int, db: Session = Depends(get_db)):
    scene = db.query(ScriptScene).filter(ScriptScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    llm = LLMService()
    script_text = f"""
场景：{scene.location}
时间：{scene.time_of_day}
人物：{scene.characters}
服装：{scene.costumes}
道具：{scene.props}
动作：{scene.actions}
对白：{scene.dialogue}
"""
    
    shot_list = await llm.generate_shot_list(script_text)
    
    # Create shots in database
    shots = []
    for shot_data in shot_list:
        shot = Shot(
            scene_id=scene_id,
            shot_number=shot_data.get("shot_number", len(shots) + 1),
            shot_size=shot_data.get("shot_size", "medium"),
            camera_position=shot_data.get("camera_position", ""),
            camera_movement=shot_data.get("camera_movement", ""),
            action=shot_data.get("action", ""),
            estimated_duration=shot_data.get("estimated_duration", 3.0),
            continuity_source=shot_data.get("continuity_source", True),
            edit_transition=shot_data.get("edit_transition", "cut")
        )
        db.add(shot)
        shots.append(shot)
    
    db.commit()
    return shots

# Generation job endpoints
@router.post("/jobs", response_model=GenerationJobResponse)
async def create_job(job: dict, db: Session = Depends(get_db)):
    db_job = GenerationJob(**job)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # Add to task queue
    await task_queue.add_job(db_job.id, db_job.job_type, db_job.priority)
    
    return db_job

@router.get("/jobs", response_model=List[GenerationJobResponse])
def list_jobs(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(GenerationJob)
    if status:
        query = query.filter(GenerationJob.status == status)
    jobs = query.order_by(GenerationJob.created_at.desc()).limit(100).all()
    return jobs

@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.status = "cancelled"
    db.commit()
    
    return {"status": "cancelled"}

# Continuity endpoints
@router.get("/shots/{shot_id}/continuity", response_model=dict)
def check_shot_continuity(shot_id: int, db: Session = Depends(get_db)):
    """Check continuity requirements for a shot"""
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    continuity = ContinuityService(db)
    return continuity.check_continuity_requirements(shot)

@router.get("/shots/{shot_id}/dependencies")
def get_shot_dependencies(shot_id: int, db: Session = Depends(get_db)):
    """Get all upstream dependencies for a shot"""
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    continuity = ContinuityService(db)
    return {"dependencies": continuity.get_shot_dependencies(shot_id)}

@router.post("/shots/{shot_id}/mark-downstream-expired")
def mark_downstream_expired(shot_id: int, db: Session = Depends(get_db)):
    """Mark downstream shots as expired when this shot changes"""
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    continuity = ContinuityService(db)
    affected = continuity.mark_downstream_expired(shot_id)
    
    return {"affected_shots": affected}

@router.get("/scenes/{scene_id}/validate-continuity")
def validate_scene_continuity(scene_id: int, db: Session = Depends(get_db)):
    """Validate continuity chain for a scene"""
    continuity = ContinuityService(db)
    return continuity.validate_continuity_chain(scene_id)

# TTS/Audio endpoints
@router.get("/tts/voices")
async def get_available_voices():
    """Get list of available TTS voices"""
    tts = TTSService()
    voices = await tts.get_available_voices()
    return {"voices": voices}

@router.post("/audio/generate-dialogue")
async def generate_dialogue(request: dict, db: Session = Depends(get_db)):
    """Generate dialogue audio for a character"""
    tts = TTSService()
    
    text = request.get("text", "")
    voice_id = request.get("voice_id", "")
    shot_id = request.get("shot_id")
    emotion = request.get("emotion")
    speed = request.get("speed", 1.0)
    
    if not text or not voice_id:
        raise HTTPException(status_code=400, detail="Text and voice_id required")
    
    # Generate output path
    output_filename = f"dialogue_{shot_id}_{voice_id}.wav"
    output_path = str(settings.UPLOADS_DIR / "audios" / output_filename)
    
    result = await tts.generate_speech(
        text=text,
        voice_id=voice_id,
        output_path=output_path,
        emotion=emotion,
        speed=speed
    )
    
    # Create asset version
    asset = AssetVersion(
        asset_type="audio",
        shot_id=shot_id,
        file_path=output_path,
        metadata=result
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return {"asset_id": asset.id, "file_path": output_path, "duration": result.get("duration")}

@router.post("/audio/generate-subtitles")
async def generate_subtitles(request: dict, db: Session = Depends(get_db)):
    """Generate SRT subtitles from dialogue timestamps"""
    ffmpeg = FFmpegService()
    
    timestamps = request.get("timestamps", [])
    episode_id = request.get("episode_id")
    
    if not timestamps:
        raise HTTPException(status_code=400, detail="Timestamps required")
    
    # Generate output path
    output_filename = f"episode_{episode_id}_subtitles.srt"
    output_path = str(settings.UPLOADS_DIR / "exports" / output_filename)
    
    success = ffmpeg.generate_srt(timestamps, output_path)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate SRT")
    
    return {"file_path": output_path}

# Export endpoints
@router.post("/export/episode/{episode_id}")
async def export_episode(episode_id: int, request: dict, db: Session = Depends(get_db)):
    """Export final episode video"""
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    ffmpeg = FFmpegService()
    
    # Get all shots for this episode
    scenes = db.query(ScriptScene).filter(ScriptScene.episode_id == episode_id).all()
    shot_ids = []
    for scene in scenes:
        shots = db.query(Shot).filter(Shot.scene_id == scene.id).all()
        shot_ids.extend([s.id for s in shots])
    
    # Get selected video versions
    video_clips = []
    for shot_id in shot_ids:
        shot = db.query(Shot).filter(Shot.id == shot_id).first()
        if shot and shot.current_video_version_id:
            version = db.query(AssetVersion).filter(AssetVersion.id == shot.current_video_version_id).first()
            if version and version.file_path:
                video_clips.append({
                    "path": version.file_path,
                    "transition": shot.edit_transition.value if shot.edit_transition else "cut"
                })
    
    if not video_clips:
        raise HTTPException(status_code=400, detail="No video clips found for export")
    
    # Generate output path
    export_type = request.get("export_type", "with_subtitles")
    output_filename = f"episode_{episode.episode_number}_{export_type}.mp4"
    output_path = str(settings.UPLOADS_DIR / "exports" / output_filename)
    
    # Normalize and export with correct specs
    success = ffmpeg.export_with_specs(
        input_path=video_clips[0]["path"],  # Simplified - would concatenate all
        output_path=output_path,
        target_width=settings.VIDEO_WIDTH,
        target_height=settings.VIDEO_HEIGHT,
        target_fps=settings.VIDEO_FPS,
        pixel_format="yuv420p"
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Export failed")
    
    # Create export job record
    export_job = ExportJob(
        project_id=episode.project_id,
        episode_id=episode_id,
        export_type=export_type,
        output_path=output_path,
        status=StageStatus.COMPLETED
    )
    db.add(export_job)
    db.commit()
    
    return {
        "export_job_id": export_job.id,
        "output_path": output_path,
        "specs": {
            "width": settings.VIDEO_WIDTH,
            "height": settings.VIDEO_HEIGHT,
            "fps": settings.VIDEO_FPS,
            "pixel_format": "yuv420p"
        }
    }

@router.get("/export/verify/{export_job_id}")
def verify_export(export_job_id: int, db: Session = Depends(get_db)):
    """Verify exported video meets specifications"""
    export_job = db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
    if not export_job:
        raise HTTPException(status_code=404, detail="Export job not found")
    
    ffmpeg = FFmpegService()
    
    try:
        info = ffmpeg.probe_video(export_job.output_path)
        
        # Verify specs
        video_stream = None
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break
        
        if not video_stream:
            return {"valid": False, "error": "No video stream found"}
        
        issues = []
        
        # Check resolution
        if video_stream.get("width") != settings.VIDEO_WIDTH:
            issues.append(f"Width mismatch: {video_stream.get('width')} != {settings.VIDEO_WIDTH}")
        if video_stream.get("height") != settings.VIDEO_HEIGHT:
            issues.append(f"Height mismatch: {video_stream.get('height')} != {settings.VIDEO_HEIGHT}")
        
        # Check FPS
        fps = eval(video_stream.get("r_frame_rate", "0/1")) if video_stream.get("r_frame_rate") else 0
        if abs(fps - settings.VIDEO_FPS) > 0.1:
            issues.append(f"FPS mismatch: {fps} != {settings.VIDEO_FPS}")
        
        # Check pixel format
        if video_stream.get("pix_fmt") != "yuv420p":
            issues.append(f"Pixel format mismatch: {video_stream.get('pix_fmt')} != yuv420p")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "info": {
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "fps": fps,
                "pix_fmt": video_stream.get("pix_fmt"),
                "codec": video_stream.get("codec_name"),
                "duration": info.get("format", {}).get("duration")
            }
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}

# WebSocket for real-time updates
@router.websocket("/ws/queue")
async def websocket_queue(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send queue status
            from ..services.task_queue import task_queue
            queue_info = await task_queue.comfyui.get_queue_info() if hasattr(task_queue, 'comfyui') else {}
            await websocket.send_json({
                "type": "queue_status",
                "data": queue_info
            })
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        pass
