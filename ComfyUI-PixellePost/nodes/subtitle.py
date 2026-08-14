"""
Subtitle rendering nodes for ComfyUI-PixellePost plugin.

Nodes:
- PixelleRenderSubtitle: Generate ASS subtitle file from shot data
"""

import json
from typing import Dict, Any, Tuple, Optional
import os

from ..core.dto import Shot, SubtitleStyle, SubtitleEvent


class PixelleRenderSubtitle:
    """
    Render subtitles for a shot.
    
    This node generates an ASS subtitle file based on the shot's
    subtitle text and style configuration.
    """
    
    CATEGORY = "Pixelle/Post"
    FUNCTION = "render_subtitle"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("ass_path", "ass_content")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "shot_json": ("STRING", {"multiline": True}),
                "canvas_width": ("INT", {"default": 720, "min": 64, "max": 3840}),
                "canvas_height": ("INT", {"default": 1280, "min": 64, "max": 3840}),
            },
            "optional": {
                "font_name": ("STRING", {"multiline": False, "default": "Microsoft YaHei"}),
                "font_size": ("INT", {"default": 42, "min": 8, "max": 200}),
                "font_color": ("STRING", {"multiline": False, "default": "#FFFFFF"}),
                "outline_color": ("STRING", {"multiline": False, "default": "#000000"}),
                "outline_width": ("INT", {"default": 3, "min": 0, "max": 10}),
                "position": (["bottom", "center", "top"],),
                "margin_bottom": ("INT", {"default": 120, "min": 0, "max": 500}),
                "output_dir": ("STRING", {"multiline": False, "default": ""}),
            }
        }
    
    def render_subtitle(
        self,
        shot_json: str,
        canvas_width: int,
        canvas_height: int,
        font_name: str = "Microsoft YaHei",
        font_size: int = 42,
        font_color: str = "#FFFFFF",
        outline_color: str = "#000000",
        outline_width: int = 3,
        position: str = "bottom",
        margin_bottom: int = 120,
        output_dir: str = "",
    ) -> Tuple[str, str]:
        """
        Render subtitle for a shot.
        
        Args:
            shot_json: JSON representation of a Shot object
            canvas_width: Canvas width for positioning
            canvas_height: Canvas height for positioning
            font_name: Font name
            font_size: Font size
            font_color: Font color in hex
            outline_color: Outline color in hex
            outline_width: Outline width
            position: Subtitle position (bottom, center, top)
            margin_bottom: Bottom margin in pixels
            output_dir: Output directory (uses temp if empty)
            
        Returns:
            Tuple of (ASS file path, ASS file content)
        """
        from ..core.subtitle_service import SubtitleService
        
        # Parse shot
        shot_data = json.loads(shot_json)
        shot = Shot.from_dict(shot_data)
        
        # Build subtitle style
        style = SubtitleStyle(
            font_name=font_name,
            font_size=font_size,
            font_color=font_color,
            outline_color=outline_color,
            outline_width=outline_width,
            position=position,
            margin_bottom=margin_bottom,
        )
        
        # Determine output directory
        if not output_dir:
            # Use ComfyUI temp directory
            try:
                import folder_paths
                output_dir = folder_paths.get_temp_directory()
            except ImportError:
                output_dir = os.path.join(os.getcwd(), "temp")
        
        # Create output path
        output_path = os.path.join(output_dir, f"subtitle_{shot.index:03d}.ass")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate ASS file
        service = SubtitleService()
        ass_path = service.generate_ass(
            events=shot.subtitle,
            style=style,
            output_path=output_path,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )
        
        # Read content for preview
        with open(ass_path, 'r', encoding='utf-8-sig') as f:
            ass_content = f.read()
        
        return (ass_path, ass_content)
