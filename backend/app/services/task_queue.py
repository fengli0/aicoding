# Task queue service for background job processing
import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from ..db.database import SessionLocal
from ..models.schemas import GenerationJob, JobStatus, AssetVersion
from ..core.config import settings

class TaskQueue:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running_jobs: Dict[int, dict] = {}
        self._processor_task: Optional[asyncio.Task] = None
        
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
    
    async def add_job(self, job_id: int, job_type: str, priority: int = 0):
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
                db = SessionLocal()
                try:
                    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
                    if job and job.status == JobStatus.PENDING:
                        await self._execute_job(db, job)
                finally:
                    db.close()
                
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing job: {e}")
    
    async def _execute_job(self, db: Session, job: GenerationJob):
        """Execute a generation job"""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        db.commit()
        
        try:
            if job.job_type == "video":
                await self._execute_video_job(db, job)
            elif job.job_type == "image":
                await self._execute_image_job(db, job)
            elif job.job_type == "audio":
                await self._execute_audio_job(db, job)
            elif job.job_type == "llm":
                await self._execute_llm_job(db, job)
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
        except Exception as e:
            job.retry_count += 1
            if job.retry_count < job.max_retries:
                # Re-queue for retry
                job.status = JobStatus.PENDING
                await self.add_job(job.id, job.job_type, job.priority)
            else:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now()
        
        db.commit()
    
    async def _execute_video_job(self, db: Session, job: GenerationJob):
        """Execute a video generation job via ComfyUI"""
        from ..services.comfyui_service import ComfyUIService
        
        comfyui = ComfyUIService()
        input_data = job.input_data
        
        # Check workflow availability
        if not await comfyui.check_workflow(input_data.get("workflow_path")):
            raise Exception("ComfyUI workflow not available")
        
        # Submit to ComfyUI
        prompt_id = await comfyui.submit_workflow(
            workflow=input_data.get("workflow"),
            prompts=input_data.get("prompts"),
            references=input_data.get("references"),
            params=input_data.get("params", {})
        )
        
        job.comfyui_prompt_id = prompt_id
        db.commit()
        
        # Wait for completion
        result = await comfyui.wait_for_completion(prompt_id)
        
        if result["status"] == "success":
            # Create asset version
            output_file = result["output_files"][0] if result.get("output_files") else None
            if output_file:
                asset_version = AssetVersion(
                    asset_type="video",
                    shot_id=input_data.get("shot_id"),
                    prompt_bundle_id=input_data.get("prompt_bundle_id"),
                    job_id=job.id,
                    file_path=output_file,
                    metadata={
                        "model": input_data.get("model"),
                        "workflow_version": input_data.get("workflow_version"),
                        "params": input_data.get("params"),
                        "seed": input_data.get("seed")
                    },
                    dependencies=input_data.get("dependencies", [])
                )
                db.add(asset_version)
                db.commit()
        else:
            raise Exception(result.get("error", "Unknown error"))
    
    async def _execute_image_job(self, db: Session, job: GenerationJob):
        """Execute an image generation job"""
        # Similar structure to video job but for images
        input_data = job.input_data
        
        # Placeholder implementation
        asset_version = AssetVersion(
            asset_type="image",
            shot_id=input_data.get("shot_id"),
            prompt_bundle_id=input_data.get("prompt_bundle_id"),
            job_id=job.id,
            file_path=f"/tmp/generated_{job.id}.png",
            metadata=input_data,
            dependencies=input_data.get("dependencies", [])
        )
        db.add(asset_version)
        db.commit()
    
    async def _execute_audio_job(self, db: Session, job: GenerationJob):
        """Execute an audio generation job"""
        input_data = job.input_data
        
        # Placeholder implementation
        asset_version = AssetVersion(
            asset_type="audio",
            job_id=job.id,
            file_path=f"/tmp/generated_{job.id}.wav",
            metadata=input_data
        )
        db.add(asset_version)
        db.commit()
    
    async def _execute_llm_job(self, db: Session, job: GenerationJob):
        """Execute an LLM generation job"""
        from ..services.llm_service import LLMService
        
        llm = LLMService()
        input_data = job.input_data
        
        result = await llm.generate(
            prompt=input_data.get("prompt"),
            system_prompt=input_data.get("system_prompt"),
            model=input_data.get("model")
        )
        
        # Store result in job metadata or create appropriate record
        job.input_data["result"] = result
        db.commit()

# Global task queue instance
task_queue = TaskQueue()
