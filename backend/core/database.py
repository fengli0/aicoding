"""
数据库核心模块
SQLite 保存结构化数据与任务状态
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import uuid


class Database:
    """SQLite 数据库管理类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 项目表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    episode_count INTEGER DEFAULT 0,
                    current_episode INTEGER DEFAULT 1,
                    production_stage TEXT DEFAULT 'novel',
                    task_progress REAL DEFAULT 0.0,
                    disk_usage_mb REAL DEFAULT 0.0,
                    last_error TEXT,
                    settings TEXT DEFAULT '{}',
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
                    title TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    core_conflict TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    script_status TEXT DEFAULT 'draft',
                    storyboard_status TEXT DEFAULT 'draft',
                    asset_status TEXT DEFAULT 'draft',
                    video_status TEXT DEFAULT 'draft',
                    audio_status TEXT DEFAULT 'draft',
                    composite_status TEXT DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            ''')
            
            # 实体档案表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entity_profiles (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    aliases TEXT DEFAULT '[]',
                    description TEXT DEFAULT '',
                    prompt_base TEXT DEFAULT '',
                    negative_prompt TEXT DEFAULT '',
                    model_params TEXT DEFAULT '{}',
                    seed INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            ''')
            
            # 实体变体表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entity_variants (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    variant_type TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    prompt_modifiers TEXT DEFAULT '[]',
                    reference_image_id TEXT,
                    is_locked INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (entity_id) REFERENCES entity_profiles(id) ON DELETE CASCADE
                )
            ''')
            
            # 剧本场次表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS script_scenes (
                    id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    scene_number INTEGER NOT NULL,
                    location TEXT DEFAULT '',
                    time_of_day TEXT DEFAULT '',
                    interior_exterior TEXT DEFAULT 'INT',
                    characters TEXT DEFAULT '[]',
                    costumes TEXT DEFAULT '{}',
                    props TEXT DEFAULT '[]',
                    actions TEXT DEFAULT '',
                    dialogues TEXT DEFAULT '[]',
                    narration TEXT DEFAULT '',
                    audio_requirements TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
                )
            ''')
            
            # 分镜镜头表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shots (
                    id TEXT PRIMARY KEY,
                    scene_id TEXT NOT NULL,
                    shot_number INTEGER NOT NULL,
                    shot_size TEXT DEFAULT 'medium',
                    camera_position TEXT DEFAULT '',
                    camera_movement TEXT DEFAULT 'static',
                    action TEXT DEFAULT '',
                    dialogue TEXT DEFAULT '',
                    narration TEXT DEFAULT '',
                    estimated_duration REAL DEFAULT 0.0,
                    frame_start_state TEXT DEFAULT '',
                    frame_end_state TEXT DEFAULT '',
                    continuity_source TEXT DEFAULT 'auto',
                    continuity_ref_shot_id TEXT,
                    edit_transition TEXT DEFAULT 'cut',
                    transition_duration REAL DEFAULT 0.0,
                    characters TEXT DEFAULT '[]',
                    scene_ref TEXT,
                    prop_refs TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (scene_id) REFERENCES script_scenes(id) ON DELETE CASCADE
                )
            ''')
            
            # 提示词包表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prompt_bundles (
                    id TEXT PRIMARY KEY,
                    shot_id TEXT NOT NULL,
                    character_prompts TEXT DEFAULT '{}',
                    scene_prompt TEXT DEFAULT '',
                    prop_prompts TEXT DEFAULT '{}',
                    shot_prompt TEXT DEFAULT '',
                    full_prompt TEXT DEFAULT '',
                    negative_prompt TEXT DEFAULT '',
                    model_name TEXT DEFAULT '',
                    model_params TEXT DEFAULT '{}',
                    seed INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (shot_id) REFERENCES shots(id) ON DELETE CASCADE
                )
            ''')
            
            # 素材版本表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_versions (
                    id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    entity_id TEXT,
                    shot_id TEXT,
                    version_number INTEGER DEFAULT 1,
                    file_path TEXT DEFAULT '',
                    thumbnail_path TEXT DEFAULT '',
                    model_name TEXT DEFAULT '',
                    workflow_version TEXT DEFAULT '',
                    parameters TEXT DEFAULT '{}',
                    seed INTEGER,
                    input_assets TEXT DEFAULT '[]',
                    dependency_versions TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'draft',
                    error_message TEXT,
                    width INTEGER DEFAULT 0,
                    height INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0.0,
                    fps INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    is_current INTEGER DEFAULT 0,
                    FOREIGN KEY (shot_id) REFERENCES shots(id) ON DELETE SET NULL
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
                    parameters TEXT DEFAULT '{}',
                    workflow_json TEXT,
                    status TEXT DEFAULT 'draft',
                    progress REAL DEFAULT 0.0,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2,
                    comfyui_job_id TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            ''')
            
            # 时间线片段表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timeline_clips (
                    id TEXT PRIMARY KEY,
                    track_type TEXT NOT NULL,
                    position REAL DEFAULT 0.0,
                    duration REAL DEFAULT 0.0,
                    asset_version_id TEXT,
                    shot_id TEXT,
                    transition TEXT DEFAULT 'cut',
                    transition_duration REAL DEFAULT 0.0,
                    volume REAL DEFAULT 1.0,
                    fade_in REAL DEFAULT 0.0,
                    fade_out REAL DEFAULT 0.0,
                    subtitle_text TEXT DEFAULT '',
                    subtitle_style TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (asset_version_id) REFERENCES asset_versions(id) ON DELETE SET NULL
                )
            ''')
            
            # 导出任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS export_jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    episode_id TEXT,
                    export_type TEXT NOT NULL,
                    output_format TEXT DEFAULT 'mp4',
                    include_subtitles INTEGER DEFAULT 1,
                    include_master INTEGER DEFAULT 1,
                    export_srt INTEGER DEFAULT 1,
                    resolution TEXT DEFAULT '1920x1080',
                    fps INTEGER DEFAULT 25,
                    codec TEXT DEFAULT 'h264',
                    audio_codec TEXT DEFAULT 'aac',
                    audio_sample_rate INTEGER DEFAULT 48000,
                    pixel_format TEXT DEFAULT 'yuv420p',
                    status TEXT DEFAULT 'draft',
                    progress REAL DEFAULT 0.0,
                    error_message TEXT,
                    output_files TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_project ON entity_profiles(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scenes_episode ON script_scenes(episode_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_shots_scene ON shots(scene_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_shot ON asset_versions(shot_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_project ON generation_jobs(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON generation_jobs(status)')
