# Task queue service for background job processing
import asyncio
import json
import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

class TaskQueue:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running_jobs: Dict[str, dict] = {}
        self._processor_task: Optional[asyncio.Task] = None
        self.db_path = 'data/dramacraft.db'
        
    def get_db(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db
        
    async def start(self):
        """Start the background job processor"""
        if self._processor_task is None:
            self._processor_task = asyncio.create_task(self._process_queue())
    
    async def stop(self):
        """Stop the background job processor"""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
    
    async def add_job(self, job_id: str, job_type: str, priority: int = 0):
        """Add a job to the queue"""
        await self.queue.put({
            "job_id": job_id,
            "job_type": job_type,
            "priority": priority,
            "added_at": datetime.now()
        })
    
    async def _process_queue(self):
        """Process jobs from the queue"""
        while True:
            try:
                job_info = await self.queue.get()
                job_id = job_info["job_id"]
                
                # Get job from database
                db = self.get_db()
                cursor = db.cursor()
                try:
                    cursor.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
                    row = cursor.fetchone()
                    if row and row['status'] == 'pending':
                        await self._execute_job(db, row)
                finally:
                    db.close()
                
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing job: {e}")
    
    async def _execute_job(self, db: sqlite3.Connection, job: sqlite3.Row):
        """Execute a generation job"""
        cursor = db.cursor()
        cursor.execute('''
            UPDATE generation_jobs SET status = 'running', started_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (job['id'],))
        db.commit()
        
        try:
            if job['job_type'] == 'video':
                await self._execute_video_job(db, job)
            elif job['job_type'] == 'image':
                await self._execute_image_job(db, job)
            elif job['job_type'] == 'audio':
                await self._execute_audio_job(db, job)
            elif job['job_type'] == 'llm':
                await self._execute_llm_job(db, job)
            
            cursor.execute('''
                UPDATE generation_jobs SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (job['id'],))
        except Exception as e:
            retry_count = job['retry_count'] + 1
            if retry_count < job['max_retries']:
                # Re-queue for retry
                cursor.execute('''
                    UPDATE generation_jobs SET status = 'pending', retry_count = ?
                    WHERE id = ?
                ''', (retry_count, job['id']))
                await self.add_job(job['id'], job['job_type'], job['priority'])
            else:
                cursor.execute('''
                    UPDATE generation_jobs SET status = 'failed', error_message = ?, retry_count = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (str(e), retry_count, job['id']))
        
        db.commit()
    
    async def _execute_video_job(self, db: sqlite3.Connection, job: sqlite3.Row):
        """Execute a video generation job via ComfyUI"""
        from .comfyui_service import ComfyUIService
        
        comfyui = ComfyUIService()
        input_data = json.loads(job['parameters'] or '{}')
        
        # Check workflow availability
        workflow_path = input_data.get("workflow_path", "workflows/minimax_h3_video.json")
        if not await comfyui.check_workflow(workflow_path):
            raise Exception("ComfyUI workflow not available")
        
        # Submit to ComfyUI
        prompt_id = await comfyui.submit_workflow(
            workflow=input_data.get("workflow"),
            prompts=input_data.get("prompts"),
            references=input_data.get("references"),
            params=input_data.get("params", {})
        )
        
        # Update job with ComfyUI prompt ID
        cursor = db.cursor()
        cursor.execute('''
            UPDATE generation_jobs SET comfyui_job_id = ? WHERE id = ?
        ''', (prompt_id, job['id']))
        db.commit()
        
        # Wait for completion
        result = await comfyui.wait_for_completion(prompt_id)
        
        if result["status"] == "success":
            # Create asset version
            output_file = result["output_files"][0] if result.get("output_files") else None
            if output_file:
                cursor.execute('''
                    INSERT INTO asset_versions (asset_type, shot_id, file_path, model_name, workflow_version, parameters, seed, status, is_current)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', 1)
                ''', ('video', input_data.get("shot_id"), output_file, 
                      input_data.get("model", ""), input_data.get("workflow_version", ""),
                      json.dumps(input_data.get("params", {})), input_data.get("seed")))
                db.commit()
        else:
            raise Exception(result.get("error", "Unknown error"))
    
    async def _execute_image_job(self, db: sqlite3.Connection, job: sqlite3.Row):
        """Execute an image generation job"""
        input_data = json.loads(job['parameters'] or '{}')
        
        # Placeholder implementation
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO asset_versions (asset_type, shot_id, file_path, model_name, parameters, status, is_current)
            VALUES (?, ?, ?, ?, ?, 'completed', 1)
        ''', ('image', input_data.get("shot_id"), f"/tmp/generated_{job['id']}.png",
              input_data.get("model", ""), json.dumps(input_data)))
        db.commit()
    
    async def _execute_audio_job(self, db: sqlite3.Connection, job: sqlite3.Row):
        """Execute an audio generation job"""
        input_data = json.loads(job['parameters'] or '{}')
        
        # Placeholder implementation
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO asset_versions (asset_type, file_path, model_name, status, is_current)
            VALUES (?, ?, ?, 'completed', 1)
        ''', ('audio', f"/tmp/generated_{job['id']}.wav", input_data.get("model", "")))
        db.commit()
    
    async def _execute_llm_job(self, db: sqlite3.Connection, job: sqlite3.Row):
        """Execute an LLM generation job"""
        from .llm_service import LLMService
        
        llm = LLMService()
        input_data = json.loads(job['parameters'] or '{}')
        
        result = await llm.generate(
            prompt=input_data.get("prompt"),
            system_prompt=input_data.get("system_prompt"),
            model=input_data.get("model")
        )
        
        # Store result in job parameters
        input_data["result"] = result
        cursor = db.cursor()
        cursor.execute('''
            UPDATE generation_jobs SET parameters = ? WHERE id = ?
        ''', (json.dumps(input_data), job['id']))
        db.commit()

# Global task queue instance
task_queue = TaskQueue()
