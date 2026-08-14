"""
Path utilities for ComfyUI-PixellePost plugin.

Handles:
- Directory boundary validation
- Safe path resolution
- ComfyUI folder_paths integration
"""

from pathlib import Path
from typing import Optional, List


class PathValidator:
    """
    Validates that file paths are within allowed directories.
    
    This prevents directory traversal attacks and ensures all
    file operations stay within ComfyUI's controlled directories.
    """
    
    def __init__(self, allowed_dirs: List[str]):
        """
        Initialize with allowed base directories.
        
        Args:
            allowed_dirs: List of absolute paths to allowed base directories
        """
        self.allowed_dirs = [Path(d).resolve() for d in allowed_dirs]
    
    def validate(self, path: str) -> str:
        """
        Validate and resolve a path.
        
        Args:
            path: Path to validate
            
        Returns:
            Resolved absolute path
            
        Raises:
            ValueError: If path is outside allowed directories
        """
        resolved = Path(path).resolve()
        
        for allowed_dir in self.allowed_dirs:
            try:
                resolved.relative_to(allowed_dir)
                return str(resolved)
            except ValueError:
                continue
        
        raise ValueError(
            f"Path {path} is outside allowed directories. "
            f"Allowed: {self.allowed_dirs}"
        )
    
    def is_allowed(self, path: str) -> bool:
        """
        Check if a path is within allowed directories.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is allowed, False otherwise
        """
        try:
            self.validate(path)
            return True
        except ValueError:
            return False


def get_comfyui_dirs() -> List[str]:
    """
    Get the standard ComfyUI directory paths.
    
    This function attempts to import folder_paths from ComfyUI
    and returns the standard input/output/temp directories.
    
    Returns:
        List of absolute directory paths
    """
    try:
        import folder_paths
        dirs = []
        
        # Get output directory
        if hasattr(folder_paths, 'get_output_directory'):
            dirs.append(folder_paths.get_output_directory())
        
        # Get input directory
        if hasattr(folder_paths, 'get_input_directory'):
            dirs.append(folder_paths.get_input_directory())
        
        # Get temp directory
        if hasattr(folder_paths, 'get_temp_directory'):
            dirs.append(folder_paths.get_temp_directory())
        
        return dirs
    except ImportError:
        # Fallback to common ComfyUI paths
        import os
        cwd = os.getcwd()
        return [
            os.path.join(cwd, "output"),
            os.path.join(cwd, "input"),
            os.path.join(cwd, "temp"),
        ]


def create_safe_path_validator() -> PathValidator:
    """
    Create a PathValidator with ComfyUI's standard directories.
    
    Returns:
        Configured PathValidator instance
    """
    return PathValidator(get_comfyui_dirs())
