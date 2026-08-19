# Core configuration and settings
import os
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
UPLOADS_DIR = BASE_DIR / "uploads"
DATABASE_URL = f"sqlite:///{BASE_DIR}/dramagen.db"

# Ensure directories exist
PROJECTS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

class Settings:
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # Video specs
    VIDEO_WIDTH: int = 1920
    VIDEO_HEIGHT: int = 1080
    VIDEO_FPS: int = 25
    MIN_EPISODE_DURATION: int = 180  # 3 minutes
    MAX_EPISODE_DURATION: int = 480  # 8 minutes
    
    # Generation limits
    MAX_CONCURRENT_VIDEO_JOBS: int = 1
    VIDEO_RETRY_COUNT: int = 2
    
    # ComfyUI
    COMFYUI_URL: str = "http://127.0.0.1:8188"
    COMFYUI_WORKFLOW_PATH: Optional[str] = None
    
    # FFmpeg
    FFMPEG_PATH: str = "ffmpeg"
    
    # TTS & LLM (configurable via UI)
    TTS_SERVICE_URL: Optional[str] = None
    LLM_SERVICE_URL: Optional[str] = None
    
    @classmethod
    def get_project_dir(cls, project_id: str) -> Path:
        return PROJECTS_DIR / project_id
    
    @classmethod
    def ensure_project_dirs(cls, project_id: str) -> Path:
        proj_dir = cls.get_project_dir(project_id)
        for subdir in ["scripts", "storyboards", "assets", "videos", "audios", "exports"]:
            (proj_dir / subdir).mkdir(parents=True, exist_ok=True)
        return proj_dir

settings = Settings()
