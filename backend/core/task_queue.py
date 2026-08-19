"""
后台持久化任务队列
应用重启后可恢复未完成任务，并从 ComfyUI 查询已提交任务的实际状态
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import asdict
import uuid

from ..core.database import Database
from shared.types.models import GenerationJob, StageStatus


class TaskQueue:
    """持久化任务队列管理器"""
    
    def __init__(self, db: Database):
        self.db = db
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._job_handlers: Dict[str, Callable] = {}
        self._shutdown_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None
    
    def register_handler(self, job_type: str, handler: Callable):
        """注册任务处理器"""
        self._job_handlers[job_type] = handler
    
    async def start_worker(self):
        """启动后台工作线程"""
        self._worker_task = asyncio.create_task(self._process_queue())
    
    async def stop_worker(self):
        """停止后台工作线程"""
        self._shutdown_event.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有运行中的任务
        for job_id, task in list(self._running_jobs.items()):
            task.cancel()
    
    async def _process_queue(self):
        """处理任务队列"""
        while not self._shutdown_event.is_set():
            try:
                # 获取待处理的任务
                pending_job = await self._get_next_pending_job()
                
                if pending_job:
                    job_id = pending_job['id']
                    
                    # 检查是否已在运行
                    if job_id not in self._running_jobs:
                        task = asyncio.create_task(self._execute_job(pending_job))
                        self._running_jobs[job_id] = task
                        
                        # 任务完成后清理
                        task.add_done_callback(lambda t, jid=job_id: self._running_jobs.pop(jid, None))
                
                # 等待一段时间后再次检查
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Task queue error: {e}")
                await asyncio.sleep(5.0)
    
    async def _get_next_pending_job(self) -> Optional[Dict]:
        """获取下一个待处理的任务"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取优先级最高的待处理或重试任务
            cursor.execute('''
                SELECT * FROM generation_jobs 
                WHERE status IN ('draft', 'failed') 
                AND retry_count < max_retries
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            if row:
                return dict(row)
        
        return None
    
    async def _execute_job(self, job_data: Dict):
        """执行单个任务"""
        job_id = job_data['id']
        job_type = job_data['job_type']
        
        try:
            # 更新状态为生成中
            self._update_job_status(job_id, StageStatus.GENERATING, started_at=datetime.now())
            
            # 获取处理器
            handler = self._job_handlers.get(job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job_type}")
            
            # 执行任务
            result = await handler(job_data)
            
            # 更新状态为完成
            self._update_job_status(
                job_id, 
                StageStatus.COMPLETED,
                progress=1.0,
                completed_at=datetime.now()
            )
            
            return result
            
        except asyncio.CancelledError:
            self._update_job_status(
                job_id,
                StageStatus.FAILED,
                error_message="Task cancelled"
            )
            raise
            
        except Exception as e:
            error_msg = str(e)
            
            # 更新重试计数
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE generation_jobs 
                    SET retry_count = retry_count + 1,
                        status = 'failed',
                        error_message = ?
                    WHERE id = ?
                ''', (error_msg, job_id))
            
            # 如果还有重试次数，重新设置为 draft 状态
            if job_data['retry_count'] + 1 < job_data['max_retries']:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE generation_jobs 
                        SET status = 'draft'
                        WHERE id = ?
                    ''', (job_id,))
            else:
                self._update_job_status(
                    job_id,
                    StageStatus.FAILED,
                    error_message=error_msg
                )
    
    def _update_job_status(
        self,
        job_id: str,
        status: StageStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        """更新任务状态"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            updates = ["status = ?"]
            params = [status.value]
            
            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)
            
            if started_at is not None:
                updates.append("started_at = ?")
                params.append(started_at.isoformat())
            
            if completed_at is not None:
                updates.append("completed_at = ?")
                params.append(completed_at.isoformat())
            
            params.append(job_id)
            
            cursor.execute(f'''
                UPDATE generation_jobs 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
    
    async def submit_job(self, job: GenerationJob) -> str:
        """提交新任务到队列"""
        job_id = job.id or str(uuid.uuid4())
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO generation_jobs (
                    id, job_type, priority, project_id, episode_id, shot_id, asset_id,
                    parameters, workflow_json, status, max_retries, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_id,
                job.job_type,
                job.priority,
                job.project_id,
                job.episode_id,
                job.shot_id,
                job.asset_id,
                json.dumps(job.parameters),
                job.workflow_json,
                job.status.value,
                job.max_retries,
                job.created_at.isoformat()
            ))
        
        return job_id
    
    async def cancel_job(self, job_id: str):
        """取消任务"""
        if job_id in self._running_jobs:
            self._running_jobs[job_id].cancel()
        
        self._update_job_status(
            job_id,
            StageStatus.FAILED,
            error_message="Cancelled by user"
        )
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """获取任务状态"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM generation_jobs WHERE id = ?', (job_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def get_pending_jobs(self, project_id: Optional[str] = None) -> List[Dict]:
        """获取待处理任务列表"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            if project_id:
                cursor.execute('''
                    SELECT * FROM generation_jobs 
                    WHERE status IN ('draft', 'generating', 'failed')
                    AND project_id = ?
                    ORDER BY priority DESC, created_at ASC
                ''', (project_id,))
            else:
                cursor.execute('''
                    SELECT * FROM generation_jobs 
                    WHERE status IN ('draft', 'generating', 'failed')
                    ORDER BY priority DESC, created_at ASC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
