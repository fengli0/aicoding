"""
ComfyUI-PixellePost: Pixelle 后期合成 ComfyUI 插件

字幕、分镜片段合成、音画时长对齐、视频拼接和 BGM
"""

from .nodes.shot import PixelleCreateShot, PixelleBuildShots
from .nodes.subtitle import PixelleRenderSubtitle
from .nodes.compose import PixelleComposeScene, PixelleComposeStoryboard
from .nodes.concat import PixelleConcatVideo, PixelleSaveVideo

NODE_CLASS_MAPPINGS = {
    "PixelleCreateShot": PixelleCreateShot,
    "PixelleBuildShots": PixelleBuildShots,
    "PixelleRenderSubtitle": PixelleRenderSubtitle,
    "PixelleComposeScene": PixelleComposeScene,
    "PixelleComposeStoryboard": PixelleComposeStoryboard,
    "PixelleConcatVideo": PixelleConcatVideo,
    "PixelleSaveVideo": PixelleSaveVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PixelleCreateShot": "Pixelle Create Shot",
    "PixelleBuildShots": "Pixelle Build Shots",
    "PixelleRenderSubtitle": "Pixelle Render Subtitle",
    "PixelleComposeScene": "Pixelle Compose Scene",
    "PixelleComposeStoryboard": "Pixelle Compose Storyboard",
    "PixelleConcatVideo": "Pixelle Concat Video",
    "PixelleSaveVideo": "Pixelle Save Video",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
