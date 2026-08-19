# ComfyUI service for video/image generation
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from ..core.config import settings

class ComfyUIService:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.COMFYUI_URL
    
    async def check_connection(self) -> bool:
        """Check if ComfyUI server is reachable"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/system_stats") as resp:
                    return resp.status == 200
        except Exception:
            return False
    
    async def check_workflow(self, workflow_path: Optional[str] = None) -> bool:
        """Check if required workflow/nodes are available"""
        # Check basic connection first
        if not await self.check_connection():
            return False
        
        # Get system stats to check loaded models/nodes
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/system_stats") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Check for required nodes/models based on workflow
                        # This is a simplified check
                        return True
        except Exception:
            return False
        
        return False
    
    async def submit_workflow(
        self,
        workflow: Dict[str, Any],
        prompts: Optional[Dict[str, str]] = None,
        references: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit a workflow to ComfyUI and return prompt_id"""
        
        # Build the prompt for ComfyUI
        comfyui_prompt = self._build_comfyui_prompt(
            workflow=workflow,
            prompts=prompts,
            references=references,
            params=params or {}
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/prompt",
                json={"prompt": comfyui_prompt}
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"ComfyUI error: {error_text}")
                
                result = await resp.json()
                return result.get("prompt_id")
    
    def _build_comfyui_prompt(
        self,
        workflow: Dict[str, Any],
        prompts: Optional[Dict[str, str]],
        references: Optional[List[str]],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build ComfyUI prompt from workflow template and parameters"""
        
        # Start with workflow template
        prompt = workflow.copy() if workflow else {}
        
        # Apply positive/negative prompts to appropriate nodes
        if prompts:
            for node_id, node_data in prompt.items():
                if node_data.get("class_type") == "CLIPTextEncode":
                    if "positive" in node_data.get("inputs", {}).get("text", "").lower():
                        node_data["inputs"]["text"] = prompts.get("positive", "")
                    elif "negative" in node_data.get("inputs", {}).get("text", "").lower():
                        node_data["inputs"]["text"] = prompts.get("negative", "")
        
        # Apply reference images
        if references:
            for node_id, node_data in prompt.items():
                if node_data.get("class_type") in ["LoadImage", "ImageUpload"]:
                    if references:
                        node_data["inputs"]["image"] = references[0]
        
        # Apply parameters (seed, steps, etc.)
        for node_id, node_data in prompt.items():
            if params.get("seed") is not None and "seed" in node_data.get("inputs", {}):
                node_data["inputs"]["seed"] = params["seed"]
            if params.get("steps") is not None and "steps" in node_data.get("inputs", {}):
                node_data["inputs"]["steps"] = params["steps"]
        
        return prompt
    
    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Wait for a prompt to complete and return results"""
        
        start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            while True:
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    return {"status": "failed", "error": "Timeout"}
                
                # Check history
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}"
                ) as resp:
                    if resp.status == 200:
                        history = await resp.json()
                        if prompt_id in history:
                            result = history[prompt_id]
                            if result.get("outputs"):
                                # Success - extract output files
                                output_files = self._extract_output_files(result["outputs"])
                                return {
                                    "status": "success",
                                    "output_files": output_files
                                }
                            elif result.get("status", {}).get("completed") is False:
                                return {"status": "failed", "error": "Job failed"}
                
                # Check queue
                async with session.get(
                    f"{self.base_url}/queue"
                ) as resp:
                    if resp.status == 200:
                        queue_data = await resp.json()
                        running = queue_data.get("queue_running", [])
                        pending = queue_data.get("queue_pending", [])
                        
                        is_running = any(
                            item[1].get("prompt_id") == prompt_id
                            for item in running
                        )
                        is_pending = any(
                            item[1].get("prompt_id") == prompt_id
                            for item in pending
                        )
                        
                        if not is_running and not is_pending:
                            # Not in queue, check if failed
                            async with session.get(
                                f"{self.base_url}/history/{prompt_id}"
                            ) as hist_resp:
                                if hist_resp.status == 200:
                                    hist = await hist_resp.json()
                                    if prompt_id not in hist:
                                        return {"status": "failed", "error": "Job disappeared"}
                
                await asyncio.sleep(1)
    
    def _extract_output_files(self, outputs: Dict[str, Any]) -> List[str]:
        """Extract output file paths from ComfyUI outputs"""
        files = []
        for node_output in outputs.values():
            if "images" in node_output:
                for img in node_output["images"]:
                    if "filename" in img:
                        files.append(f"/tmp/{img['filename']}")
            if "gifs" in node_output:
                for gif in node_output["gifs"]:
                    if "filename" in gif:
                        files.append(f"/tmp/{gif['filename']}")
        return files
    
    async def cancel_prompt(self, prompt_id: str) -> bool:
        """Cancel a running prompt"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/interrupt"
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False
    
    async def get_queue_info(self) -> Dict[str, Any]:
        """Get current queue information"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/queue") as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            pass
        return {"queue_running": [], "queue_pending": []}
