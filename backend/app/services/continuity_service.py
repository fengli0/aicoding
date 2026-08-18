# Continuity management service for maintaining visual consistency across shots
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from ..models.schemas import Shot, AssetVersion, StageStatus, ScriptScene

class ContinuityService:
    """
    Manages visual continuity between shots.
    
    Key principles:
    - Same scene + continuous action = inherit from previous shot's last frame
    - Scene change or time jump = use character/scene reference images
    - Hard cut = don't inherit, use current shot's references
    - When upstream version changes, mark downstream as expired
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_continuity_requirements(self, shot: Shot) -> Dict[str, Any]:
        """
        Determine what references a shot needs based on continuity rules.
        
        Returns:
            Dictionary with:
            - should_inherit: bool
            - reason: str
            - depends_on_shot_id: Optional[int]
            - reference_type: str (last_frame | character_ref | scene_ref)
        """
        # Get previous shot in same scene
        prev_shot = self.db.query(Shot).filter(
            Shot.scene_id == shot.scene_id,
            Shot.shot_number == shot.shot_number - 1
        ).first()
        
        # Get current scene info
        scene = self.db.query(ScriptScene).filter(
            ScriptScene.id == shot.scene_id
        ).first()
        
        if not scene:
            return {
                "should_inherit": False,
                "reason": "Scene not found",
                "reference_type": "character_ref"
            }
        
        # Check if this is the first shot
        if not prev_shot:
            return {
                "should_inherit": False,
                "reason": "First shot in scene",
                "reference_type": "character_ref"
            }
        
        # Check if there's a hard cut or scene change
        if shot.edit_transition in ["fade_in", "fade_out"]:
            return {
                "should_inherit": False,
                "reason": f"Transition type: {shot.edit_transition.value}",
                "reference_type": "character_ref"
            }
        
        # If continuity_source is explicitly False, don't inherit
        if not shot.continuity_source:
            return {
                "should_inherit": False,
                "reason": "Continuity source disabled",
                "reference_type": "character_ref"
            }
        
        # Check if scenes match (same location and time)
        prev_scene = self.db.query(ScriptScene).filter(
            ScriptScene.id == prev_shot.scene_id
        ).first()
        
        if not prev_scene:
            return {
                "should_inherit": False,
                "reason": "Previous scene not found",
                "reference_type": "character_ref"
            }
        
        # Compare scene properties
        scene_changed = (
            scene.location != prev_scene.location or
            scene.time_of_day != prev_scene.time_of_day
        )
        
        if scene_changed:
            return {
                "should_inherit": False,
                "reason": "Scene or time changed",
                "reference_type": "character_ref"
            }
        
        # Check if previous shot has a valid selected version
        prev_selected_version = None
        if hasattr(prev_shot, 'current_video_version_id') and prev_shot.current_video_version_id:
            prev_selected_version = self.db.query(AssetVersion).filter(
                AssetVersion.id == prev_shot.current_video_version_id
            ).first()
        
        if not prev_selected_version:
            return {
                "should_inherit": False,
                "reason": "Previous shot has no selected version",
                "reference_type": "character_ref"
            }
        
        # All checks passed - can inherit from previous shot
        return {
            "should_inherit": True,
            "reason": "Continuous shot in same scene",
            "depends_on_shot_id": prev_shot.id,
            "depends_on_version_id": prev_selected_version.id,
            "reference_type": "last_frame"
        }
    
    def get_continuity_reference(self, shot: Shot) -> Optional[str]:
        """
        Get the actual reference file path for a shot.
        
        Returns:
            File path to reference image/frame, or None
        """
        requirements = self.check_continuity_requirements(shot)
        
        if not requirements["should_inherit"]:
            # Return character/scene reference instead
            # This would come from EntityVariant or PromptBundle
            return None
        
        # Get the previous shot's selected version
        prev_shot_id = requirements.get("depends_on_shot_id")
        if not prev_shot_id:
            return None
        
        prev_shot = self.db.query(Shot).filter(Shot.id == prev_shot_id).first()
        if not prev_shot or not prev_shot.current_video_version_id:
            return None
        
        # Extract last frame from previous video
        prev_version = self.db.query(AssetVersion).filter(
            AssetVersion.id == prev_shot.current_video_version_id
        ).first()
        
        if not prev_version or not prev_version.file_path:
            return None
        
        # In production, this would extract the actual last frame
        # For now, return the video path (FFmpeg service will extract frame)
        return prev_version.file_path
    
    def mark_downstream_expired(self, shot_id: int, version_change: bool = True) -> List[int]:
        """
        Mark all shots that depend on this shot as expired when upstream changes.
        
        Args:
            shot_id: The shot that was modified
            version_change: Whether it's a version switch (vs content edit)
        
        Returns:
            List of shot IDs marked as expired
        """
        affected_shots = []
        
        # Get the modified shot
        shot = self.db.query(Shot).filter(Shot.id == shot_id).first()
        if not shot:
            return affected_shots
        
        # Find all shots in the same scene with higher shot numbers
        downstream_shots = self.db.query(Shot).filter(
            Shot.scene_id == shot.scene_id,
            Shot.shot_number > shot.shot_number
        ).all()
        
        for ds in downstream_shots:
            # Check if this shot inherits from upstream
            requirements = self.check_continuity_requirements(ds)
            
            if requirements.get("should_inherit"):
                # Check if the dependency chain leads back to modified shot
                dep_shot_id = requirements.get("depends_on_shot_id")
                
                # Simple check: if directly depends on modified shot
                if dep_shot_id == shot_id or version_change:
                    if ds.status != StageStatus.EXPIRED:
                        ds.status = StageStatus.EXPIRED
                        affected_shots.append(ds.id)
        
        self.db.commit()
        return affected_shots
    
    def validate_continuity_chain(self, scene_id: int) -> Dict[str, Any]:
        """
        Validate the entire continuity chain for a scene.
        
        Returns:
            Dictionary with validation results and any breaks in the chain
        """
        shots = self.db.query(Shot).filter(
            Shot.scene_id == scene_id
        ).order_by(Shot.shot_number).all()
        
        if not shots:
            return {"valid": True, "breaks": [], "warnings": []}
        
        breaks = []
        warnings = []
        
        for i, shot in enumerate(shots):
            if i == 0:
                continue  # First shot doesn't need continuity
            
            prev_shot = shots[i - 1]
            
            # Check if previous shot has a selected version
            if not prev_shot.current_video_version_id:
                if shot.continuity_source:
                    warnings.append({
                        "shot_id": shot.id,
                        "shot_number": shot.shot_number,
                        "issue": "Previous shot has no selected version"
                    })
                continue
            
            # Check if continuity is properly set up
            if shot.continuity_source:
                # Should have a valid dependency
                reqs = self.check_continuity_requirements(shot)
                if not reqs["should_inherit"]:
                    warnings.append({
                        "shot_id": shot.id,
                        "shot_number": shot.shot_number,
                        "issue": f"Continuity enabled but cannot inherit: {reqs['reason']}"
                    })
        
        return {
            "valid": len(breaks) == 0,
            "breaks": breaks,
            "warnings": warnings
        }
    
    def get_shot_dependencies(self, shot_id: int) -> List[Dict[str, Any]]:
        """
        Get all upstream dependencies for a shot.
        
        Returns:
            List of dependency info dictionaries
        """
        dependencies = []
        
        shot = self.db.query(Shot).filter(Shot.id == shot_id).first()
        if not shot:
            return dependencies
        
        # Trace back through continuity chain
        current_shot = shot
        visited = set()
        
        while current_shot and current_shot.id not in visited:
            visited.add(current_shot.id)
            
            if current_shot.shot_number <= 1:
                break
            
            # Find previous shot
            prev_shot = self.db.query(Shot).filter(
                Shot.scene_id == current_shot.scene_id,
                Shot.shot_number == current_shot.shot_number - 1
            ).first()
            
            if not prev_shot:
                break
            
            # Check if continuity applies
            reqs = self.check_continuity_requirements(current_shot)
            if not reqs.get("should_inherit"):
                break
            
            # Add dependency
            dependencies.append({
                "shot_id": prev_shot.id,
                "shot_number": prev_shot.shot_number,
                "version_id": prev_shot.current_video_version_id,
                "dependency_type": "continuity"
            })
            
            current_shot = prev_shot
        
        return dependencies
