"""
JobStore for managing task directories, state, and file locks.

Handles:
- Task directory creation under ComfyUI output/temp
- State persistence (state.json)
- Content hashing for cache/reuse detection
- File locking to prevent concurrent writes
"""

import hashlib
import json
import os
import fcntl
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .dto import Manifest, Shot, ShotStatus


class JobStore:
    """
    Manages job-specific directories and state files.
    
    Directory structure:
    output/pixelle_post/<job_id>/
      manifest.json
      state.json
      scenes/scene_001.mp4
      scenes/scene_002.mp4
      subtitles/scene_001.ass
      final.mp4
    """
    
    def __init__(self, base_output_dir: str, job_id: str):
        self.job_id = job_id
        self.base_output_dir = Path(base_output_dir)
        self.job_dir = self.base_output_dir / "pixelle_post" / job_id
        self.scenes_dir = self.job_dir / "scenes"
        self.subtitles_dir = self.job_dir / "subtitles"
        self.temp_dir = self.job_dir / "temp"
        
        self.manifest_path = self.job_dir / "manifest.json"
        self.state_path = self.job_dir / "state.json"
        self.lock_path = self.job_dir / ".lock"
        
        self._lock_fd: Optional[int] = None
    
    def ensure_dirs(self) -> None:
        """Create all necessary directories."""
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.scenes_dir.mkdir(exist_ok=True)
        self.subtitles_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    def acquire_lock(self) -> bool:
        """
        Acquire an exclusive lock on the job directory.
        
        Returns True if lock acquired, False if already locked.
        """
        self.ensure_dirs()
        try:
            self._lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, OSError):
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            return False
    
    def release_lock(self) -> None:
        """Release the exclusive lock."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except (IOError, OSError):
                pass
            finally:
                self._lock_fd = None
    
    def save_manifest(self, manifest: Manifest) -> None:
        """Save manifest to disk."""
        self.ensure_dirs()
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            f.write(manifest.to_json())
    
    def load_manifest(self) -> Optional[Manifest]:
        """Load manifest from disk."""
        if not self.manifest_path.exists():
            return None
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Manifest.from_dict(data)
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Save job state to disk."""
        self.ensure_dirs()
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load job state from disk."""
        if not self.state_path.exists():
            return None
        with open(self.state_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_scene_path(self, index: int) -> Path:
        """Get the path for a scene video file."""
        self.ensure_dirs()
        return self.scenes_dir / f"scene_{index:03d}.mp4"
    
    def get_subtitle_path(self, index: int) -> Path:
        """Get the path for a subtitle file."""
        self.ensure_dirs()
        return self.subtitles_dir / f"scene_{index:03d}.ass"
    
    def get_temp_path(self, name: str) -> Path:
        """Get a path in the temp directory."""
        self.ensure_dirs()
        return self.temp_dir / name
    
    def get_final_path(self) -> Path:
        """Get the path for the final composed video."""
        self.ensure_dirs()
        return self.job_dir / "final.mp4"
    
    @staticmethod
    def compute_content_hash(data: Dict[str, Any]) -> str:
        """
        Compute a content hash for cache key generation.
        
        This includes plugin version, canvas params, subtitle style,
        and shot input hashes - not just the user-provided job_id.
        """
        import hashlib
        hasher = hashlib.sha256()
        
        # Sort keys for deterministic hashing
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hasher.update(serialized.encode('utf-8'))
        
        return hasher.hexdigest()[:16]
    
    def init_state(self, manifest: Manifest) -> Dict[str, Any]:
        """
        Initialize state from manifest.
        
        Returns the initial state dict.
        """
        shots_state = {}
        for shot in manifest.shots:
            shots_state[str(shot.index)] = {
                "status": ShotStatus.PENDING.value,
                "output_path": None,
                "duration": None,
                "error_message": None,
                "input_hash": None,
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        state = {
            "job_id": manifest.job_id,
            "schema_version": manifest.schema_version,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "shots": shots_state,
            "final_output": None,
        }
        
        self.save_state(state)
        return state
    
    def update_shot_state(
        self,
        index: int,
        status: ShotStatus,
        output_path: Optional[str] = None,
        duration: Optional[float] = None,
        error_message: Optional[str] = None,
        input_hash: Optional[str] = None,
    ) -> None:
        """Update the state of a single shot."""
        state = self.load_state()
        if state is None:
            raise RuntimeError(f"State not found for job {self.job_id}")
        
        shot_key = str(index)
        if shot_key not in state["shots"]:
            state["shots"][shot_key] = {}
        
        state["shots"][shot_key].update({
            "status": status.value,
            "output_path": output_path,
            "duration": duration,
            "error_message": error_message,
            "input_hash": input_hash,
            "updated_at": datetime.utcnow().isoformat(),
        })
        state["updated_at"] = datetime.utcnow().isoformat()
        
        self.save_state(state)
    
    def get_completed_shots(self) -> List[int]:
        """Get indices of completed shots."""
        state = self.load_state()
        if state is None:
            return []
        
        completed = []
        for idx_str, shot_state in state.get("shots", {}).items():
            if shot_state.get("status") == ShotStatus.COMPLETED.value:
                completed.append(int(idx_str))
        
        return sorted(completed)
    
    def get_failed_shots(self) -> List[int]:
        """Get indices of failed shots."""
        state = self.load_state()
        if state is None:
            return []
        
        failed = []
        for idx_str, shot_state in state.get("shots", {}).items():
            if shot_state.get("status") == ShotStatus.FAILED.value:
                failed.append(int(idx_str))
        
        return sorted(failed)
    
    def can_reuse_shot(self, index: int, current_hash: str) -> bool:
        """
        Check if a shot can be reused based on input hash.
        
        Returns True if the shot is completed and has the same input hash.
        """
        state = self.load_state()
        if state is None:
            return False
        
        shot_key = str(index)
        shot_state = state.get("shots", {}).get(shot_key)
        if shot_state is None:
            return False
        
        if shot_state.get("status") != ShotStatus.COMPLETED.value:
            return False
        
        stored_hash = shot_state.get("input_hash")
        if stored_hash != current_hash:
            return False
        
        # Verify output file exists
        output_path = shot_state.get("output_path")
        if output_path is None or not Path(output_path).exists():
            return False
        
        return True
    
    def set_final_output(self, path: str) -> None:
        """Set the final output path in state."""
        state = self.load_state()
        if state is None:
            raise RuntimeError(f"State not found for job {self.job_id}")
        
        state["final_output"] = {
            "path": path,
            "created_at": datetime.utcnow().isoformat(),
        }
        state["updated_at"] = datetime.utcnow().isoformat()
        
        self.save_state(state)
