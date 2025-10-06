# -*- coding: utf-8 -*-
import os
import sys

# 确保输出不被缓冲
os.environ['PYTHONUNBUFFERED'] = '1'
import json
import random
import io
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from collections import deque
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import load_presets, save_presets, load_user_settings, save_user_settings
from comfyui_client import ComfyUIClient
from workflow_processor import load_workflow, process_workflow, validate_workflow_params

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 配置日志 - 直接输出到stdout，无缓冲
print("=" * 50, flush=True)
print("Discord ComfyUI Bot (Python Version)", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Discord.py: {discord.__version__}", flush=True)
print(f"Platform: {sys.platform}", flush=True)
print(f"Working Dir: {os.getcwd()}", flush=True)
print("=" * 50, flush=True)

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
COMFYUI_URL = os.getenv('COMFYUI_URL', 'http://localhost:8188')
WORKFLOW_PATH = Path(__file__).parent / 'workflow.json'
WORKFLOW_JSON_ENV = os.getenv('WORKFLOW_JSON')  # 可选：从环境变量读取工作流

# 检查环境变量
print(f"Discord Token: {'✓ Found' if DISCORD_TOKEN else '✗ Missing'}", flush=True)
print(f"ComfyUI URL: {COMFYUI_URL}", flush=True)
print(f"Workflow Source: {'Environment Variable' if WORKFLOW_JSON_ENV else f'File ({WORKFLOW_PATH})'}", flush=True)
print(f"Environment: {'Zeabur' if os.getenv('ZEABUR') else 'Local/Docker'}", flush=True)

if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found!", flush=True)
    print("Please set DISCORD_TOKEN in environment variables", flush=True)
    import time
    while True:
        time.sleep(60)
        print("Waiting for DISCORD_TOKEN...", flush=True)

print("Configuration OK, starting bot...", flush=True)

# 任务队列
task_queue = deque()
is_generating = False
queue_lock = asyncio.Lock()

# 面板状态缓存
panel_states = {}

# ComfyUI 客户端
comfy_client = ComfyUIClient(COMFYUI_URL)

# 工作流模板
try:
    # 优先从环境变量加载，如果没有则从文件加载
    if WORKFLOW_JSON_ENV:
        print("Loading workflow from environment variable...", flush=True)
        workflow_template = json.loads(WORKFLOW_JSON_ENV)
    else:
        print(f"Loading workflow from file: {WORKFLOW_PATH}", flush=True)
        workflow_template = load_workflow(str(WORKFLOW_PATH))

    required_params = validate_workflow_params(workflow_template)
    print(f"Workflow loaded successfully! Required params: {required_params}", flush=True)
except Exception as e:
    print(f"ERROR: Failed to load workflow: {e}", flush=True)
    workflow_template = {}
    required_params = []

# 可用的采样器和调度器（将在启动时从 ComfyUI 获取）
SAMPLERS = []
SCHEDULERS = []

# 尺寸预设
SIZE_PRESETS = {
    'portrait_s': {'width': 512, 'height': 768},
    'portrait_m': {'width': 832, 'height': 1216},
    'landscape_s': {'width': 768, 'height': 512},
    'landscape_m': {'width': 1216, 'height': 832},
    'square_s': {'width': 512, 'height': 512},
    'square_m': {'width': 768, 'height': 768},
    'square_l': {'width': 832, 'height': 832},
    'hd': {'width': 1024, 'height': 1024}
}

# 尺寸限制
SIZE_LIMITS = {
    'maxPixels': 1024 * 1536,
    'maxWidth': 2048,
    'maxHeight': 2048
}

class ComfyUIBot(commands.Bot):
    def __init__(self):
        print("Initializing ComfyUIBot...", flush=True)
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        print("ComfyUIBot initialized", flush=True)

    async def setup_hook(self):
        print("Setting up bot commands...", flush=True)
        try:
            # 添加预设命令组
            self.tree.add_command(PresetGroup())
            print("Added PresetGroup command", flush=True)

            # 从 ComfyUI 获取采样器和调度器
            await self.fetch_comfyui_options()

            # 同步命令
            synced = await self.tree.sync()
            print(f'Commands synced successfully! Synced {len(synced)} commands', flush=True)
        except Exception as e:
            print(f"Error in setup_hook: {e}", flush=True)
            import traceback
            traceback.print_exc()

    async def fetch_comfyui_options(self):
        """从 ComfyUI 获取可用的采样器和调度器"""
        global SAMPLERS, SCHEDULERS
        try:
            print("Fetching samplers and schedulers from ComfyUI...", flush=True)
            SAMPLERS = await comfy_client.get_samplers()
            SCHEDULERS = await comfy_client.get_schedulers()
            print(f"Fetched {len(SAMPLERS)} samplers and {len(SCHEDULERS)} schedulers", flush=True)
        except Exception as e:
            print(f"Warning: Failed to fetch ComfyUI options: {e}", flush=True)
            # 使用默认值
            SAMPLERS = ['euler', 'euler_ancestral', 'dpmpp_2m', 'dpmpp_sde']
            SCHEDULERS = ['normal', 'karras', 'exponential', 'simple']

bot = ComfyUIBot()

async def generate_image(params: Dict[str, Any]) -> tuple[bytes, int]:
    """调用 ComfyUI API 生成图片"""
    logger.debug(f"生成参数: size={params['width']}x{params['height']}, steps={params.get('steps', 20)}")

    # 准备工作流参数
    workflow_params = {
        'width': params['width'],
        'height': params['height'],
        'prompt': params['prompt'],
        'imprompt': params.get('negative_prompt', ''),
        'seed': params.get('seed', random.randint(0, 2147483647)),
        'steps': params.get('steps', 20),
        'cfg_scale': params.get('cfg_scale', 7.0),
        'sampler_name': params.get('sampler_name', 'euler'),
        'schedule': params.get('scheduler', 'normal')
    }

    # 处理工作流
    workflow = process_workflow(workflow_template, workflow_params)

    logger.info(f"Submitting workflow to ComfyUI...")

    try:
        # 生成图片
        image_data, outputs = await comfy_client.generate_image(workflow, timeout=300)
        logger.info(f"Image generated successfully, size: {len(image_data)/1024:.2f} KB")
        return image_data, workflow_params['seed']

    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise e

async def process_queue():
    """处理任务队列"""
    global is_generating

    async with queue_lock:
        if is_generating or not task_queue:
            return

        is_generating = True
        task = task_queue.popleft()

    interaction = task['interaction']
    params = task['params']
    user_id = interaction.user.id
    user_name = str(interaction.user)
    start_time = datetime.now()

    logger.info(f"[生成开始] 用户: {user_name} (ID: {user_id}) | 尺寸: {params['width']}x{params['height']} | 队列剩余: {len(task_queue)}")

    try:
        # 设置超时时间为5分钟
        async with asyncio.timeout(300):
            # 生成图片
            logger.info(f"[API调用] 用户: {user_name} | 正在调用 ComfyUI API...")
            image_data, seed = await generate_image(params)

            # 发送图片
            file = discord.File(
                fp=io.BytesIO(image_data),
                filename=f'comfyui_{seed}.png'
            )

            embed = discord.Embed(
                title='✅ 生成完成',
                color=discord.Color.green()
            )
            embed.add_field(name='Seed', value=str(seed), inline=True)
            embed.add_field(name='Size', value=f"{params['width']}x{params['height']}", inline=True)
            embed.add_field(name='Steps', value=str(params.get('steps', 20)), inline=True)
            embed.add_field(name='CFG', value=str(params.get('cfg_scale', 7.0)), inline=True)
            embed.add_field(name='Sampler', value=params.get('sampler_name', 'euler'), inline=True)
            embed.add_field(name='Scheduler', value=params.get('scheduler', 'normal'), inline=True)

            await interaction.followup.send(embed=embed, file=file)

            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[生成成功] 用户: {user_name} | Seed: {seed} | 耗时: {elapsed_time:.2f}秒 | 队列剩余: {len(task_queue)}")

    except asyncio.TimeoutError:
        logger.error(f"[生成超时] 用户: {user_name} | 超过5分钟未响应")
        error_embed = discord.Embed(
            title='❌ 生成超时',
            description='生成请求超过5分钟未响应，请稍后重试',
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

    except Exception as e:
        logger.error(f"[生成失败] 用户: {user_name} | 错误: {str(e)}")
        error_embed = discord.Embed(
            title='❌ 生成失败',
            description=str(e),
            color=discord.Color.red()
        )
        try:
            await interaction.followup.send(embed=error_embed)
        except:
            logger.error(f"[发送失败] 无法向用户 {user_name} 发送错误消息")

    finally:
        is_generating = False
        # 继续处理队列中的下一个任务
        if task_queue:
            logger.info(f"[队列处理] 继续处理队列，剩余任务: {len(task_queue)}")
            asyncio.create_task(process_queue())

@bot.tree.command(name='comfy', description='使用 ComfyUI 生成图片')
@app_commands.describe(
    prompt='正向提示词',
    negative='负向提示词',
    width='宽度',
    height='高度',
    steps='采样步数',
    cfg_scale='CFG Scale',
    seed='种子'
)
async def comfy_command(
    interaction: discord.Interaction,
    prompt: str,
    negative: Optional[str] = None,
    width: Optional[int] = 512,
    height: Optional[int] = 768,
    steps: Optional[int] = 20,
    cfg_scale: Optional[float] = 7.0,
    seed: Optional[int] = None
):
    """ComfyUI 图片生成命令"""
    # 验证尺寸
    if (width * height > SIZE_LIMITS['maxPixels'] or
        width > SIZE_LIMITS['maxWidth'] or
        height > SIZE_LIMITS['maxHeight']):
        await interaction.response.send_message(
            f"❌ 尺寸超限！最大 {SIZE_LIMITS['maxWidth']}×{SIZE_LIMITS['maxHeight']}",
            ephemeral=True
        )
        return

    # 准备任务
    task = {
        'interaction': interaction,
        'params': {
            'prompt': prompt,
            'negative_prompt': negative or '',
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed or -1,
            'sampler_name': SAMPLERS[0] if SAMPLERS else 'euler',
            'scheduler': SCHEDULERS[0] if SCHEDULERS else 'normal'
        }
    }

    # 加入队列
    task_queue.append(task)
    queue_position = len(task_queue)

    logger.info(f"[队列添加] 用户: {interaction.user} (ID: {interaction.user.id}) | 队列位置: {queue_position}")

    await interaction.response.send_message(
        f'✅ 您的请求已加入队列，当前排在第 {queue_position} 位。',
        ephemeral=True
    )

    # 处理队列
    asyncio.create_task(process_queue())

@bot.tree.command(name='queue', description='查看当前队列状态')
async def queue_command(interaction: discord.Interaction):
    if not task_queue:
        await interaction.response.send_message('💭 当前队列为空', ephemeral=True)
        return

    embed = discord.Embed(
        title='📋 队列状态',
        description=f'当前有 {len(task_queue)} 个任务在队列中',
        color=discord.Color.blue()
    )

    if is_generating:
        embed.add_field(name='状态', value='🎨 正在生成中...', inline=False)
    else:
        embed.add_field(name='状态', value='✅ 空闲中', inline=False)

    # 显示队列中的前5个任务
    queue_list = list(task_queue)[:5]
    for i, task in enumerate(queue_list, 1):
        user_name = task['interaction'].user.name
        size = f"{task['params']['width']}x{task['params']['height']}"
        embed.add_field(
            name=f'位置 {i}',
            value=f'用户: {user_name}\n尺寸: {size}',
            inline=True
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='panel', description='打开一个交互式绘图面板')
async def panel_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_name = str(interaction.user)
    logger.info(f"[面板打开] 用户: {user_name} (ID: {user_id})")

    user_settings = load_user_settings()

    # 获取或创建用户设置
    if user_id not in user_settings:
        user_settings[user_id] = {
            'size': 'portrait_s',
            'width': 512,
            'height': 768,
            'steps': 20,
            'cfg_scale': 7.0,
            'sampler': SAMPLERS[0] if SAMPLERS else 'euler',
            'scheduler': SCHEDULERS[0] if SCHEDULERS else 'normal',
            'preset': None
        }
        save_user_settings(user_settings)

    state = user_settings[user_id]
    panel_states[user_id] = state

    # 构建面板
    embed = discord.Embed(
        title='🎨 ComfyUI 绘图面板',
        description='使用下方的菜单和按钮来配置您的图片生成参数',
        color=discord.Color.blue()
    )

    # 显示尺寸信息
    if state['size'] == 'custom':
        size_display = f"自定义: {state.get('width', 512)}×{state.get('height', 768)}"
    else:
        size_preset = SIZE_PRESETS.get(state['size'], {'width': 512, 'height': 768})
        size_display = f"{state['size']} ({size_preset['width']}×{size_preset['height']})"

    embed.add_field(name='尺寸', value=size_display, inline=True)
    embed.add_field(name='步数', value=str(state.get('steps', 20)), inline=True)
    embed.add_field(name='CFG', value=str(state.get('cfg_scale', 7.0)), inline=True)
    embed.add_field(name='采样器', value=state.get('sampler', 'euler'), inline=True)
    embed.add_field(name='调度器', value=state.get('scheduler', 'normal'), inline=True)
    embed.add_field(name='预设', value=state.get('preset', '未选择'), inline=True)

    # 创建选择菜单
    size_select = discord.ui.Select(
        placeholder='选择尺寸',
        options=[
            discord.SelectOption(label='📱 竖图 832×1216', value='portrait_m', default='portrait_m'==state['size']),
            discord.SelectOption(label='📱 竖图小 512×768', value='portrait_s', default='portrait_s'==state['size']),
            discord.SelectOption(label='🖼️ 横图 1216×832', value='landscape_m', default='landscape_m'==state['size']),
            discord.SelectOption(label='🖼️ 横图小 768×512', value='landscape_s', default='landscape_s'==state['size']),
            discord.SelectOption(label='⬜ 方图 512×512', value='square_s', default='square_s'==state['size']),
            discord.SelectOption(label='◻️ 方图 768×768', value='square_m', default='square_m'==state['size']),
            discord.SelectOption(label='◼ 方图 832×832', value='square_l', default='square_l'==state['size']),
            discord.SelectOption(label='🔲 方图 1024×1024', value='hd', default='hd'==state['size']),
            discord.SelectOption(label='🔧 自定义尺寸', value='custom', default='custom'==state['size'])
        ],
        custom_id='size_select',
        row=0
    )

    # 采样器选择（限制为最多25个选项）
    sampler_options = [
        discord.SelectOption(
            label=sampler[:100],  # Discord 限制标签长度
            value=sampler,
            default=sampler==state.get('sampler')
        )
        for sampler in SAMPLERS[:25]  # Discord 限制最多25个选项
    ]
    sampler_select = discord.ui.Select(
        placeholder='选择采样器',
        options=sampler_options if sampler_options else [
            discord.SelectOption(label='euler', value='euler', default=True)
        ],
        custom_id='sampler_select',
        row=1
    )

    # 调度器选择
    scheduler_options = [
        discord.SelectOption(
            label=scheduler[:100],
            value=scheduler,
            default=scheduler==state.get('scheduler')
        )
        for scheduler in SCHEDULERS[:25]
    ]
    scheduler_select = discord.ui.Select(
        placeholder='选择调度器',
        options=scheduler_options if scheduler_options else [
            discord.SelectOption(label='normal', value='normal', default=True)
        ],
        custom_id='scheduler_select',
        row=2
    )

    # 创建预设选择菜单
    presets = load_presets()
    user_presets = presets.get(user_id, {})

    preset_options = [discord.SelectOption(label='不使用预设', value='none', default=state.get('preset') is None)]
    preset_options.extend([
        discord.SelectOption(label=name, value=name, default=name==state.get('preset'))
        for name in list(user_presets.keys())[:24]  # 限制24个（加上"不使用预设"共25个）
    ])

    preset_select = discord.ui.Select(
        placeholder='选择预设',
        options=preset_options,
        custom_id='preset_select',
        row=3
    )

    # 创建按钮
    generate_button = discord.ui.Button(
        label='🎨 生成图片',
        style=discord.ButtonStyle.primary,
        custom_id='generate_button',
        row=4
    )

    save_button = discord.ui.Button(
        label='💾 保存设置',
        style=discord.ButtonStyle.success,
        custom_id='save_button',
        row=4
    )

    custom_size_button = discord.ui.Button(
        label='📐 自定义尺寸',
        style=discord.ButtonStyle.secondary,
        custom_id='custom_size_input',
        row=4
    )

    params_button = discord.ui.Button(
        label='⚙️ 高级参数',
        style=discord.ButtonStyle.secondary,
        custom_id='params_button',
        row=4
    )

    # 创建视图
    view = discord.ui.View(timeout=300)
    view.add_item(size_select)
    view.add_item(sampler_select)
    view.add_item(scheduler_select)
    view.add_item(preset_select)
    view.add_item(generate_button)
    view.add_item(save_button)
    view.add_item(custom_size_button)
    view.add_item(params_button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# 创建预设命令组
class PresetGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name='preset', description='管理你的个人提示词预设')

    @app_commands.command(name='save', description='保存一个新的预设')
    async def save_preset(
        self,
        interaction: discord.Interaction,
        name: str,
        prompt: str,
        negative: Optional[str] = None
    ):
        user_id = str(interaction.user.id)
        presets = load_presets()

        if user_id not in presets:
            presets[user_id] = {}

        presets[user_id][name] = {
            'prompt': prompt,
            'negative': negative or ''
        }

        save_presets(presets)
        await interaction.response.send_message(
            f"✅ 预设 '{name}' 已保存！",
            ephemeral=True
        )

    @app_commands.command(name='list', description='查看你所有的预设')
    async def list_presets(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        presets = load_presets()
        user_presets = presets.get(user_id, {})

        if not user_presets:
            await interaction.response.send_message(
                '你还没有保存任何预设。',
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title='你的预设',
            color=discord.Color.blue()
        )

        for name, data in user_presets.items():
            value = f"**正面:** {data['prompt'][:100]}..."
            if data.get('negative'):
                value += f"\n**负面:** {data['negative'][:100]}..."
            embed.add_field(name=name, value=value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='delete', description='删除一个预设')
    async def delete_preset(self, interaction: discord.Interaction, name: str):
        user_id = str(interaction.user.id)
        presets = load_presets()

        if user_id in presets and name in presets[user_id]:
            del presets[user_id][name]
            save_presets(presets)
            await interaction.response.send_message(
                f"🗑️ 预设 '{name}' 已删除。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ 未找到名为 '{name}' 的预设。",
                ephemeral=True
            )

    @delete_preset.autocomplete('name')
    async def delete_preset_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        presets = load_presets()
        user_presets = presets.get(user_id, {})

        return [
            app_commands.Choice(name=name, value=name)
            for name in user_presets.keys()
            if current.lower() in name.lower()
        ][:25]

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get('custom_id', '')
    user_id = str(interaction.user.id)
    user_name = str(interaction.user)

    logger.debug(f"[面板交互] 用户: {user_name} | 组件: {custom_id}")

    if user_id not in panel_states:
        await interaction.response.send_message('会话已过期，请重新打开面板', ephemeral=True)
        return

    state = panel_states[user_id]

    # 处理选择菜单
    if custom_id.endswith('_select'):
        field = custom_id.replace('_select', '')
        value = interaction.data['values'][0]

        if field == 'size':
            state['size'] = value
            # 如果选择了预设尺寸，更新宽高
            if value != 'custom' and value in SIZE_PRESETS:
                state['width'] = SIZE_PRESETS[value]['width']
                state['height'] = SIZE_PRESETS[value]['height']
        elif field == 'sampler':
            state['sampler'] = value
        elif field == 'scheduler':
            state['scheduler'] = value
        elif field == 'preset':
            if value == 'none':
                state['preset'] = None
            else:
                state['preset'] = value

        # 更新面板
        await update_panel(interaction, state)

    # 处理自定义尺寸输入按钮
    elif custom_id == 'custom_size_input':
        modal = discord.ui.Modal(title='输入自定义尺寸')

        width_input = discord.ui.TextInput(
            label='宽度',
            placeholder=f'输入宽度 (64-{SIZE_LIMITS["maxWidth"]})',
            default=str(state.get('width', 512)),
            required=True,
            max_length=4
        )

        height_input = discord.ui.TextInput(
            label='高度',
            placeholder=f'输入高度 (64-{SIZE_LIMITS["maxHeight"]})',
            default=str(state.get('height', 768)),
            required=True,
            max_length=4
        )

        modal.add_item(width_input)
        modal.add_item(height_input)

        async def size_modal_submit(modal_interaction: discord.Interaction):
            try:
                new_width = int(width_input.value)
                new_height = int(height_input.value)

                # 验证尺寸
                if new_width < 64 or new_width > SIZE_LIMITS['maxWidth']:
                    await modal_interaction.response.send_message(
                        f"❌ 宽度必须在 64 到 {SIZE_LIMITS['maxWidth']} 之间",
                        ephemeral=True
                    )
                    return

                if new_height < 64 or new_height > SIZE_LIMITS['maxHeight']:
                    await modal_interaction.response.send_message(
                        f"❌ 高度必须在 64 到 {SIZE_LIMITS['maxHeight']} 之间",
                        ephemeral=True
                    )
                    return

                if new_width * new_height > SIZE_LIMITS['maxPixels']:
                    await modal_interaction.response.send_message(
                        f"❌ 总像素数不能超过 {SIZE_LIMITS['maxPixels']:,}",
                        ephemeral=True
                    )
                    return

                # 确保尺寸是64的倍数
                new_width = (new_width // 64) * 64
                new_height = (new_height // 64) * 64

                state['size'] = 'custom'
                state['width'] = new_width
                state['height'] = new_height

                await update_panel(modal_interaction, state)

            except ValueError:
                await modal_interaction.response.send_message(
                    '❌ 请输入有效的数字',
                    ephemeral=True
                )

        modal.on_submit = size_modal_submit
        await interaction.response.send_modal(modal)

    # 处理高级参数按钮
    elif custom_id == 'params_button':
        modal = discord.ui.Modal(title='高级参数设置')

        steps_input = discord.ui.TextInput(
            label='步数 (Steps)',
            placeholder='输入采样步数 (1-150)',
            default=str(state.get('steps', 20)),
            required=True,
            max_length=3
        )

        cfg_input = discord.ui.TextInput(
            label='CFG Scale',
            placeholder='输入 CFG Scale (1.0-30.0)',
            default=str(state.get('cfg_scale', 7.0)),
            required=True,
            max_length=5
        )

        modal.add_item(steps_input)
        modal.add_item(cfg_input)

        async def params_modal_submit(modal_interaction: discord.Interaction):
            try:
                new_steps = int(steps_input.value)
                new_cfg = float(cfg_input.value)

                if new_steps < 1 or new_steps > 150:
                    await modal_interaction.response.send_message(
                        '❌ 步数必须在 1 到 150 之间',
                        ephemeral=True
                    )
                    return

                if new_cfg < 1.0 or new_cfg > 30.0:
                    await modal_interaction.response.send_message(
                        '❌ CFG Scale 必须在 1.0 到 30.0 之间',
                        ephemeral=True
                    )
                    return

                state['steps'] = new_steps
                state['cfg_scale'] = new_cfg

                await update_panel(modal_interaction, state)

            except ValueError:
                await modal_interaction.response.send_message(
                    '❌ 请输入有效的数字',
                    ephemeral=True
                )

        modal.on_submit = params_modal_submit
        await interaction.response.send_modal(modal)

    elif custom_id == 'save_button':
        user_settings = load_user_settings()
        user_settings[user_id] = state
        save_user_settings(user_settings)
        logger.info(f"[设置保存] 用户: {user_name} 保存了面板设置")
        await interaction.response.send_message('✅ 设置已保存！', ephemeral=True)

    elif custom_id == 'generate_button':
        # 创建模态框
        modal = discord.ui.Modal(title='输入提示词')

        prompt_input = discord.ui.TextInput(
            label='正面提示词',
            placeholder='输入您想要生成的图片描述...',
            required=True,
            style=discord.TextStyle.paragraph
        )

        negative_input = discord.ui.TextInput(
            label='负面提示词',
            placeholder='输入您不想要的元素...',
            required=False,
            style=discord.TextStyle.paragraph
        )

        modal.add_item(prompt_input)
        modal.add_item(negative_input)

        async def modal_submit(modal_interaction: discord.Interaction):
            prompt = prompt_input.value
            negative = negative_input.value

            # 如果选择了预设，合并提示词
            if state.get('preset'):
                presets = load_presets()
                user_presets = presets.get(user_id, {})
                if state['preset'] in user_presets:
                    preset_data = user_presets[state['preset']]
                    prompt = f"{preset_data['prompt']}, {prompt}"
                    if preset_data.get('negative'):
                        negative = f"{preset_data['negative']}, {negative}" if negative else preset_data['negative']

            # 获取尺寸
            if state['size'] == 'custom':
                width = state.get('width', 512)
                height = state.get('height', 768)
            else:
                size_data = SIZE_PRESETS.get(state['size'], SIZE_PRESETS['portrait_s'])
                width = size_data['width']
                height = size_data['height']

            # 准备任务
            task = {
                'interaction': modal_interaction,
                'params': {
                    'prompt': prompt,
                    'negative_prompt': negative,
                    'width': width,
                    'height': height,
                    'steps': state.get('steps', 20),
                    'cfg_scale': state.get('cfg_scale', 7.0),
                    'sampler_name': state.get('sampler', SAMPLERS[0] if SAMPLERS else 'euler'),
                    'scheduler': state.get('scheduler', SCHEDULERS[0] if SCHEDULERS else 'normal'),
                    'seed': -1
                }
            }

            task_queue.append(task)
            queue_position = len(task_queue)

            logger.info(f"[队列添加-面板] 用户: {modal_interaction.user} (ID: {modal_interaction.user.id}) | 队列位置: {queue_position}")

            await modal_interaction.response.send_message(
                f'✅ 您的请求已加入队列，当前排在第 {queue_position} 位。',
                ephemeral=True
            )

            asyncio.create_task(process_queue())

        modal.on_submit = modal_submit
        await interaction.response.send_modal(modal)

async def update_panel(interaction: discord.Interaction, state: Dict):
    """更新面板显示"""
    embed = discord.Embed(
        title='🎨 ComfyUI 绘图面板',
        description='使用下方的菜单和按钮来配置您的图片生成参数',
        color=discord.Color.blue()
    )

    # 显示尺寸信息
    if state['size'] == 'custom':
        size_display = f"自定义: {state.get('width', 512)}×{state.get('height', 768)}"
    else:
        size_preset = SIZE_PRESETS.get(state['size'], {'width': 512, 'height': 768})
        size_display = f"{state['size']} ({size_preset['width']}×{size_preset['height']})"

    embed.add_field(name='尺寸', value=size_display, inline=True)
    embed.add_field(name='步数', value=str(state.get('steps', 20)), inline=True)
    embed.add_field(name='CFG', value=str(state.get('cfg_scale', 7.0)), inline=True)
    embed.add_field(name='采样器', value=state.get('sampler', 'euler'), inline=True)
    embed.add_field(name='调度器', value=state.get('scheduler', 'normal'), inline=True)
    embed.add_field(name='预设', value=state.get('preset', '未选择'), inline=True)

    await interaction.response.edit_message(embed=embed)

@bot.event
async def on_ready():
    logger.info(f'[Bot启动] 登录为: {bot.user} (ID: {bot.user.id})')
    logger.info(f'[Bot启动] 连接到 {len(bot.guilds)} 个服务器')
    for guild in bot.guilds:
        logger.info(f'  - {guild.name} (ID: {guild.id}) | 成员数: {guild.member_count}')
    logger.info('[Bot启动] Bot准备就绪!')

    # 设置状态
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="/comfy | /panel | /preset"
        )
    )

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f'事件 {event} 中发生错误: {sys.exc_info()}')

async def queue_cleanup_task():
    """定期清理过期队列任务"""
    while True:
        await asyncio.sleep(300)  # 每5分钟检查一次
        if len(task_queue) > 10:
            logger.warning(f"[队列警告] 队列过长，当前有 {len(task_queue)} 个任务")
        if not is_generating and task_queue:
            logger.info(f"[队列检查] 检测到队列未处理，尝试重启队列处理")
            asyncio.create_task(process_queue())

async def main_async():
    """异步主函数"""
    async with bot:
        # 启动队列清理任务
        asyncio.create_task(queue_cleanup_task())
        await bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    logger.info("正在启动Bot...")
    logger.info(f"Token长度: {len(DISCORD_TOKEN) if DISCORD_TOKEN else 0}")

    try:
        # Windows 环境特殊处理
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # 运行 bot
        bot.run(DISCORD_TOKEN, reconnect=True, log_handler=None)
    except KeyboardInterrupt:
        logger.info("用户停止了Bot")
    except Exception as e:
        logger.error(f"启动Bot失败: {e}")
        import traceback
        traceback.print_exc()
        if os.getenv('ZEABUR'):
            import time
            while True:
                time.sleep(60)
                print(f"Waiting after error: {e}", flush=True)
        sys.exit(1)
