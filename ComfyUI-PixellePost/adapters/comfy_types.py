"""
Adapters for converting between ComfyUI types and plugin internal types.

Handles:
- IMAGE tensor to PNG file conversion
- AUDIO object to WAV file conversion
- Path validation within allowed directories
"""

import io
import torch
from pathlib import Path
from typing import Optional, Tuple, Union
from PIL import Image
import numpy as np


class ComfyTypeAdapter:
    """
    Adapter for converting ComfyUI standard types to file paths.
    
    This adapter handles:
    - IMAGE tensors ([B,H,W,C], float 0..1) -> PNG files
    - AUDIO objects (waveform, sample_rate) -> WAV files
    - Path validation within ComfyUI directories
    """
    
    def __init__(self, temp_dir: str, allowed_dirs: Optional[list] = None):
        """
        Initialize the adapter.
        
        Args:
            temp_dir: Base directory for temporary files
            allowed_dirs: List of allowed base directories for path validation
        """
        self.temp_dir = Path(temp_dir)
        self.allowed_dirs = allowed_dirs or []
    
    def image_to_png(
        self,
        image_tensor: torch.Tensor,
        filename: str,
        batch_index: int = 0,
    ) -> str:
        """
        Convert an IMAGE tensor to a PNG file.
        
        Args:
            image_tensor: ComfyUI IMAGE tensor [B,H,W,C], float 0..1
            filename: Output filename (without extension)
            batch_index: Which image from the batch to use (default: 0)
            
        Returns:
            Path to the generated PNG file
        """
        # Clamp to 0..1 and convert to uint8
        img = image_tensor[batch_index].cpu().numpy()
        img = np.clip(img * 255.0, 0, 255).astype(np.uint8)
        
        # Handle channel order (ComfyUI uses BGR or RGBA)
        if img.shape[2] == 4:
            # RGBA
            pil_img = Image.fromarray(img, mode='RGBA')
        elif img.shape[2] == 3:
            # RGB
            pil_img = Image.fromarray(img, mode='RGB')
        elif img.shape[2] == 1:
            # Grayscale
            pil_img = Image.fromarray(img[:, :, 0], mode='L')
        else:
            raise ValueError(f"Unsupported image channels: {img.shape[2]}")
        
        # Save to temp directory
        output_path = self.temp_dir / f"{filename}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pil_img.save(output_path, format='PNG')
        
        return str(output_path)
    
    def audio_to_wav(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        filename: str,
    ) -> str:
        """
        Convert an AUDIO object to a WAV file.
        
        Args:
            waveform: Audio waveform tensor [samples] or [channels, samples]
            sample_rate: Sample rate in Hz
            filename: Output filename (without extension)
            
        Returns:
            Path to the generated WAV file
        """
        import scipy.io.wavfile as wavfile
        
        # Ensure waveform is on CPU and numpy
        audio_data = waveform.cpu().numpy()
        
        # Normalize to int16 range if float
        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
            audio_data = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
        
        # Handle stereo/mono
        if len(audio_data.shape) == 2:
            # Multi-channel: take first channel or mix down
            audio_data = audio_data[0]
        
        # Save to temp directory
        output_path = self.temp_dir / f"{filename}.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wavfile.write(str(output_path), sample_rate, audio_data)
        
        return str(output_path)
    
    def validate_path(self, path: str) -> str:
        """
        Validate that a path is within allowed directories.
        
        Args:
            path: Path to validate
            
        Returns:
            Resolved absolute path
            
        Raises:
            ValueError: If path is outside allowed directories
        """
        resolved = Path(path).resolve()
        
        # Check against allowed directories
        for allowed_dir in self.allowed_dirs:
            allowed_path = Path(allowed_dir).resolve()
            try:
                resolved.relative_to(allowed_path)
                return str(resolved)
            except ValueError:
                continue
        
        # If no allowed_dirs specified, just return resolved path
        if not self.allowed_dirs:
            return str(resolved)
        
        raise ValueError(
            f"Path {path} is outside allowed directories: {self.allowed_dirs}"
        )
    
    def get_safe_temp_path(self, name: str) -> str:
        """
        Get a safe path within the temp directory.
        
        Args:
            name: Filename (will be sanitized)
            
        Returns:
            Safe path within temp directory
        """
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in '._-')
        if not safe_name:
            safe_name = "temp"
        
        path = self.temp_dir / safe_name
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)
