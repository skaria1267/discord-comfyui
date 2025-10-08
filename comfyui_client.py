# -*- coding: utf-8 -*-
import json
import uuid
import asyncio
import aiohttp
import websockets
import logging
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ComfyUIClient:
    """ComfyUI API 客户端"""

    def __init__(self, server_url: str):
        """
        初始化 ComfyUI 客户端

        Args:
            server_url: ComfyUI 服务器地址 (例如: http://localhost:8188)
        """
        self.server_url = server_url.rstrip('/')
        parsed = urlparse(self.server_url)
        ws_scheme = 'wss' if parsed.scheme == 'https' else 'ws'
        self.ws_url = f"{ws_scheme}://{parsed.netloc}/ws"
        self.client_id = str(uuid.uuid4())

        # 缓存可用的采样器和调度器
        self._samplers: Optional[List[str]] = None
        self._schedulers: Optional[List[str]] = None

    async def get_object_info(self) -> Dict[str, Any]:
        """获取所有节点信息"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.server_url}/object_info") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to get object info: {response.status} - {error_text}")
            except aiohttp.ClientError as e:
                raise Exception(f"Network error: {str(e)}")

    async def get_samplers(self) -> List[str]:
        """获取可用的采样器列表"""
        if self._samplers is not None:
            return self._samplers

        try:
            object_info = await self.get_object_info()

            # 从 KSampler 节点中获取采样器列表
            if 'KSampler' in object_info:
                ksampler_info = object_info['KSampler']
                if 'input' in ksampler_info and 'required' in ksampler_info['input']:
                    sampler_info = ksampler_info['input']['required'].get('sampler_name')
                    if sampler_info and isinstance(sampler_info, list) and len(sampler_info) > 0:
                        self._samplers = sampler_info[0]
                        logger.info(f"Found {len(self._samplers)} samplers from ComfyUI")
                        return self._samplers

            # 如果没有找到，返回默认列表
            logger.warning("Could not find samplers from ComfyUI, using defaults")
            self._samplers = [
                "euler", "euler_ancestral", "heun", "heunpp2", "dpm_2",
                "dpm_2_ancestral", "lms", "dpm_fast", "dpm_adaptive",
                "dpmpp_2s_ancestral", "dpmpp_sde", "dpmpp_sde_gpu",
                "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu",
                "dpmpp_3m_sde", "dpmpp_3m_sde_gpu", "ddpm", "lcm", "ddim", "uni_pc", "uni_pc_bh2"
            ]
            return self._samplers

        except Exception as e:
            logger.error(f"Error getting samplers: {e}")
            # 返回默认列表
            self._samplers = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"]
            return self._samplers

    async def get_schedulers(self) -> List[str]:
        """获取可用的调度器列表"""
        if self._schedulers is not None:
            return self._schedulers

        try:
            object_info = await self.get_object_info()

            # 从 KSampler 节点中获取调度器列表
            if 'KSampler' in object_info:
                ksampler_info = object_info['KSampler']
                if 'input' in ksampler_info and 'required' in ksampler_info['input']:
                    scheduler_info = ksampler_info['input']['required'].get('scheduler')
                    if scheduler_info and isinstance(scheduler_info, list) and len(scheduler_info) > 0:
                        self._schedulers = scheduler_info[0]
                        logger.info(f"Found {len(self._schedulers)} schedulers from ComfyUI")
                        return self._schedulers

            # 如果没有找到，返回默认列表
            logger.warning("Could not find schedulers from ComfyUI, using defaults")
            self._schedulers = [
                "normal", "karras", "exponential", "sgm_uniform",
                "simple", "ddim_uniform", "beta"
            ]
            return self._schedulers

        except Exception as e:
            logger.error(f"Error getting schedulers: {e}")
            # 返回默认列表
            self._schedulers = ["normal", "karras", "exponential", "simple"]
            return self._schedulers

    async def queue_prompt(self, workflow: Dict[str, Any]) -> str:
        """
        提交工作流到队列

        Args:
            workflow: 工作流 JSON

        Returns:
            prompt_id: 任务 ID
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.server_url}/prompt",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        prompt_id = result.get('prompt_id')
                        if not prompt_id:
                            raise Exception("No prompt_id in response")
                        logger.info(f"Queued prompt: {prompt_id}")
                        return prompt_id
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to queue prompt: {response.status} - {error_text}")
            except aiohttp.ClientError as e:
                raise Exception(f"Network error: {str(e)}")

    async def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """
        获取生成的图片

        Args:
            filename: 文件名
            subfolder: 子文件夹
            folder_type: 文件夹类型 (output, input, temp)

        Returns:
            图片二进制数据
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.server_url}/view",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        logger.debug(f"Downloaded image: {filename}, size: {len(image_data)/1024:.2f} KB")
                        return image_data
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to get image: {response.status} - {error_text}")
            except aiohttp.ClientError as e:
                raise Exception(f"Network error: {str(e)}")

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """
        获取任务历史记录

        Args:
            prompt_id: 任务 ID

        Returns:
            历史记录
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.server_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        history = await response.json()
                        return history.get(prompt_id, {})
                    else:
                        return {}
            except Exception as e:
                logger.debug(f"Error getting history: {e}")
                return {}

    async def wait_for_completion(self, prompt_id: str, timeout: int = 300) -> Tuple[bool, Optional[Dict]]:
        """
        等待任务完成

        Args:
            prompt_id: 任务 ID
            timeout: 超时时间（秒）

        Returns:
            (成功标志, 输出信息)
        """
        queue_remaining: Optional[int] = None
        finished_nodes: set = set()

        try:
            async with websockets.connect(
                f"{self.ws_url}?clientId={self.client_id}",
                ping_interval=None,
                close_timeout=10
            ) as websocket:
                start_time = asyncio.get_event_loop().time()

                while True:
                    # 检查超时
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        logger.error(f"Task {prompt_id} timed out after {timeout}s")
                        return False, None

                    try:
                        # 设置接收超时
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=5.0
                        )

                        data = json.loads(message)
                        msg_type = data.get('type')

                        # 执行完成
                        if msg_type == 'executed':
                            msg_data = data.get('data', {})
                            if msg_data.get('prompt_id') and msg_data.get('prompt_id') != prompt_id:
                                continue

                            node_id = msg_data.get('node')
                            if node_id:
                                finished_nodes.add(node_id)

                            output_data = msg_data.get('output', {})
                            has_images = any(
                                isinstance(value, list) and value and isinstance(value[0], dict) and 'filename' in value[0]
                                for value in output_data.values()
                            )

                            if has_images or (queue_remaining == 0 if queue_remaining is not None else False):
                                history = await self.get_history(prompt_id)
                                if history:
                                    logger.info(f"Task {prompt_id} completed successfully")
                                    return True, history.get('outputs', {})

                            if msg_data.get('node') is None:
                                # Workflow finished
                                history = await self.get_history(prompt_id)
                                if history:
                                    logger.info(f"Task {prompt_id} completed successfully")
                                    return True, history.get('outputs', {})

                        elif msg_type == 'status':
                            status_data = data.get('data', {})
                            exec_info = status_data.get('status', {}).get('exec_info', {})
                            if isinstance(exec_info, dict) and 'queue_remaining' in exec_info:
                                queue_remaining = exec_info['queue_remaining']
                                if queue_remaining == 0 and finished_nodes:
                                    history = await self.get_history(prompt_id)
                                    if history:
                                        logger.info(f"Task {prompt_id} completed successfully (status)")
                                        return True, history.get('outputs', {})

                        # Progress update
                        elif msg_type == 'progress':
                            progress_data = data.get('data', {})
                            current = progress_data.get('value', 0)
                            maximum = progress_data.get('max', 0)
                            if maximum > 0:
                                logger.debug(f"Progress: {current}/{maximum} ({current/maximum*100:.1f}%)")

                        # 执行出错
                        elif msg_type == 'execution_error':
                            error_data = data.get('data', {})
                            logger.error(f"Execution error: {error_data}")
                            return False, None

                    except asyncio.TimeoutError:
                        # 接收超时，继续等待
                        continue
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON decode error: {e}")
                        continue

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            # WebSocket 失败时，尝试轮询 history
            return await self._poll_history(prompt_id, timeout)

    async def _poll_history(self, prompt_id: str, timeout: int) -> Tuple[bool, Optional[Dict]]:
        """通过轮询 history 来等待任务完成（WebSocket 失败时的备用方案）"""
        start_time = asyncio.get_event_loop().time()

        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.error(f"Task {prompt_id} timed out (polling)")
                return False, None

            history = await self.get_history(prompt_id)
            if history and 'outputs' in history:
                logger.info(f"Task {prompt_id} completed (polling)")
                return True, history['outputs']

            await asyncio.sleep(2)

    async def generate_image(self, workflow: Dict[str, Any], timeout: int = 300) -> Tuple[bytes, Dict]:
        """
        生成图片（一站式方法）

        Args:
            workflow: 工作流 JSON
            timeout: 超时时间（秒）

        Returns:
            (图片数据, 输出信息)
        """
        # 提交任务
        prompt_id = await self.queue_prompt(workflow)

        # 等待完成
        success, outputs = await self.wait_for_completion(prompt_id, timeout)

        if not success or not outputs:
            raise Exception("Image generation failed or timed out")

        # 获取图片
        # 查找 SaveImage 节点的输出
        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                images = node_output['images']
                if images and len(images) > 0:
                    image_info = images[0]
                    filename = image_info.get('filename')
                    subfolder = image_info.get('subfolder', '')
                    folder_type = image_info.get('type', 'output')

                    if filename:
                        image_data = await self.get_image(filename, subfolder, folder_type)
                        return image_data, outputs

        raise Exception("No image found in outputs")
