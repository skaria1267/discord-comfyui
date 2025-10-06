#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ComfyUI Discord Bot 启动脚本
提供更详细的启动日志和错误处理
"""
import os
import sys
import logging
from pathlib import Path

# 确保输出不被缓冲
os.environ['PYTHONUNBUFFERED'] = '1'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def check_requirements():
    """检查必需的文件和配置"""
    logger.info("检查项目配置...")

    # 检查必需文件
    required_files = [
        'main.py',
        'utils.py',
        'comfyui_client.py',
        'workflow_processor.py',
        'workflow.json',
        'requirements.txt'
    ]

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        logger.error(f"缺少必需文件: {', '.join(missing_files)}")
        return False

    # 检查环境变量
    from dotenv import load_dotenv
    load_dotenv()

    discord_token = os.getenv('DISCORD_TOKEN')
    comfyui_url = os.getenv('COMFYUI_URL')

    if not discord_token:
        logger.error("未设置 DISCORD_TOKEN 环境变量")
        return False

    if not comfyui_url:
        logger.warning("未设置 COMFYUI_URL，将使用默认值 http://localhost:8188")

    logger.info("配置检查完成 ✓")
    return True

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Discord ComfyUI Bot 启动脚本")
    logger.info(f"Python 版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info("=" * 60)

    # 检查配置
    if not check_requirements():
        logger.error("配置检查失败，请修复错误后重试")
        sys.exit(1)

    # 导入并运行主程序
    try:
        logger.info("正在启动 Discord Bot...")
        import main
        # main.py 会自动运行
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
