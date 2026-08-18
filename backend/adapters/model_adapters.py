"""
模型适配器接口
TTS、LLM、图片及视频模型使用独立适配器，可在设置页配置服务地址、模型、工作流和凭据并执行连通性测试
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp


@dataclass
class ModelConfig:
    """模型配置"""
    service_url: str = ""
    api_key: str = ""
    model_name: str = ""
    workflow_path: Optional[str] = None
    extra_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    data: Any = None
    error_message: Optional[str] = None
    model_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.model_info is None:
            self.model_info = {}


class BaseModelAdapter(ABC):
    """模型适配器基类"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> GenerationResult:
        """执行生成"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接"""
        pass


class LLMAdapter(BaseModelAdapter):
    """LLM 模型适配器"""
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> GenerationResult:
        """生成文本"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.config.model_name,
                    "messages": [],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                
                if system_prompt:
                    payload["messages"].append({"role": "system", "content": system_prompt})
                
                payload["messages"].append({"role": "user", "content": prompt})
                
                headers = {"Content-Type": "application/json"}
                if self.config.api_key:
                    headers["Authorization"] = f"Bearer {self.config.api_key}"
                
                async with session.post(
                    f"{self.config.service_url}/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return GenerationResult(
                            success=False,
                            error_message=f"LLM API error: {response.status} - {error_text}"
                        )
                    
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    return GenerationResult(
                        success=True,
                        data=content,
                        model_info={"model": self.config.model_name}
                    )
                    
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"LLM generation failed: {str(e)}"
            )
    
    async def test_connection(self) -> bool:
        """测试 LLM 连接"""
        try:
            result = await self.generate("Hello")
            return result.success
        except Exception:
            return False


class ImageGenerationAdapter(BaseModelAdapter):
    """图片生成适配器"""
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        seed: Optional[int] = None,
        steps: int = 30,
        cfg_scale: float = 7.0,
        reference_images: Optional[List[str]] = None,
        **kwargs
    ) -> GenerationResult:
        """生成图片"""
        try:
            async with aiohttp.ClientSession() as session:
                # ComfyUI API 调用
                workflow = self._build_comfyui_workflow(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    seed=seed or -1,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    reference_images=reference_images
                )
                
                payload = {"prompt": workflow}
                
                headers = {"Content-Type": "application/json"}
                
                async with session.post(
                    f"{self.config.service_url}/prompt",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return GenerationResult(
                            success=False,
                            error_message=f"Image API error: {response.status} - {error_text}"
                        )
                    
                    result = await response.json()
                    job_id = result.get("prompt_id")
                    
                    return GenerationResult(
                        success=True,
                        data={"job_id": job_id},
                        model_info={"model": self.config.model_name}
                    )
                    
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"Image generation failed: {str(e)}"
            )
    
    def _build_comfyui_workflow(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: int,
        steps: int,
        cfg_scale: float,
        reference_images: Optional[List[str]] = None
    ) -> Dict:
        """构建 ComfyUI 工作流 JSON"""
        # 这里应该加载实际的 workflow 模板并填充参数
        # 简化示例
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                }
            },
            "4": {"class_type": "CheckpointLoaderSimple"},
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1}
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["4", 1]}
            }
        }
        
        if reference_images:
            # 添加参考图节点
            for i, img_path in enumerate(reference_images):
                node_id = str(100 + i)
                workflow[node_id] = {
                    "class_type": "LoadImage",
                    "inputs": {"image": img_path}
                }
        
        return workflow
    
    async def test_connection(self) -> bool:
        """测试图片生成连接"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.config.service_url}/system_stats") as response:
                    return response.status == 200
        except Exception:
            return False


class VideoGenerationAdapter(BaseModelAdapter):
    """视频生成适配器 - ComfyUI Minimax H3"""
    
    async def generate(
        self,
        prompt: str,
        reference_images: Optional[List[str]] = None,
        duration: float = 5.0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 25,
        seed: Optional[int] = None,
        continuity_frame: Optional[str] = None,  # 上一镜头末帧
        **kwargs
    ) -> GenerationResult:
        """生成视频"""
        try:
            async with aiohttp.ClientSession() as session:
                # 构建 Minimax H3 工作流
                workflow = self._build_h3_workflow(
                    prompt=prompt,
                    reference_images=reference_images,
                    duration=duration,
                    width=width,
                    height=height,
                    fps=fps,
                    seed=seed or -1,
                    continuity_frame=continuity_frame
                )
                
                payload = {"prompt": workflow}
                
                headers = {"Content-Type": "application/json"}
                
                async with session.post(
                    f"{self.config.service_url}/prompt",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return GenerationResult(
                            success=False,
                            error_message=f"Video API error: {response.status} - {error_text}"
                        )
                    
                    result = await response.json()
                    job_id = result.get("prompt_id")
                    
                    return GenerationResult(
                        success=True,
                        data={"job_id": job_id},
                        model_info={"model": self.config.model_name}
                    )
                    
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"Video generation failed: {str(e)}"
            )
    
    def _build_h3_workflow(
        self,
        prompt: str,
        reference_images: Optional[List[str]],
        duration: float,
        width: int,
        height: int,
        fps: int,
        seed: int,
        continuity_frame: Optional[str]
    ) -> Dict:
        """构建 Minimax H3 工作流 JSON"""
        # 实际应该加载 H3 workflow 模板
        workflow = {
            "1": {
                "class_type": "MinimaxH3Node",
                "inputs": {
                    "prompt": prompt,
                    "seed": seed,
                    "duration": duration,
                    "width": width,
                    "height": height,
                    "fps": fps
                }
            }
        }
        
        if continuity_frame:
            workflow["2"] = {
                "class_type": "LoadImage",
                "inputs": {"image": continuity_frame}
            }
            workflow["1"]["inputs"]["first_frame"] = ["2", 0]
        
        if reference_images:
            for i, img_path in enumerate(reference_images):
                node_id = str(10 + i)
                workflow[node_id] = {
                    "class_type": "LoadImage",
                    "inputs": {"image": img_path}
                }
        
        return workflow
    
    async def check_workflow_availability(self) -> Dict[str, Any]:
        """检查 ComfyUI 工作流和模型可用性"""
        try:
            async with aiohttp.ClientSession() as session:
                # 获取已安装节点列表
                async with session.get(f"{self.config.service_url}/object_info") as response:
                    if response.status != 200:
                        return {"available": False, "error": "Cannot fetch object info"}
                    
                    object_info = await response.json()
                    
                    # 检查必需的节点
                    required_nodes = ["MinimaxH3Node", "VHS_VideoCombine"]
                    missing_nodes = []
                    
                    for node in required_nodes:
                        if node not in object_info:
                            missing_nodes.append(node)
                    
                    if missing_nodes:
                        return {
                            "available": False,
                            "error": f"Missing nodes: {', '.join(missing_nodes)}"
                        }
                    
                    return {"available": True, "nodes": list(object_info.keys())}
                    
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def test_connection(self) -> bool:
        """测试视频生成连接"""
        result = await self.check_workflow_availability()
        return result.get("available", False)


class TTSAdapter(BaseModelAdapter):
    """TTS 适配器"""
    
    async def generate(
        self,
        text: str,
        voice_id: str = "",
        emotion: str = "neutral",
        speed: float = 1.0,
        pitch: float = 1.0,
        **kwargs
    ) -> GenerationResult:
        """生成语音"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": text,
                    "voice": voice_id or self.config.model_name,
                    "emotion": emotion,
                    "speed": speed,
                    "pitch": pitch,
                }
                
                headers = {"Content-Type": "application/json"}
                if self.config.api_key:
                    headers["Authorization"] = f"Bearer {self.config.api_key}"
                
                async with session.post(
                    f"{self.config.service_url}/tts",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return GenerationResult(
                            success=False,
                            error_message=f"TTS API error: {response.status} - {error_text}"
                        )
                    
                    # 假设返回音频数据
                    audio_data = await response.read()
                    
                    return GenerationResult(
                        success=True,
                        data=audio_data,
                        model_info={"model": self.config.model_name, "voice": voice_id}
                    )
                    
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"TTS generation failed: {str(e)}"
            )
    
    async def test_connection(self) -> bool:
        """测试 TTS 连接"""
        try:
            result = await self.generate("测试", voice_id="test_voice")
            return result.success
        except Exception:
            return False


def create_adapter(adapter_type: str, config: ModelConfig) -> BaseModelAdapter:
    """工厂函数创建适配器实例"""
    adapters = {
        "llm": LLMAdapter,
        "image": ImageGenerationAdapter,
        "video": VideoGenerationAdapter,
        "tts": TTSAdapter,
    }
    
    adapter_class = adapters.get(adapter_type)
    if not adapter_class:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
    
    return adapter_class(config)
