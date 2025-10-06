# -*- coding: utf-8 -*-
import os
import json
from pathlib import Path
from typing import Dict, Any

# 根据环境变量确定数据存储路径
# Zeabur会自动提供/data目录用于持久化存储
if os.getenv('ZEABUR') or os.path.exists('/data'):
    DATA_DIR = '/data'
else:
    DATA_DIR = os.getenv('DATA_DIR', Path(__file__).parent)

PRESETS_FILE = Path(DATA_DIR) / 'user_presets.json'
SETTINGS_FILE = Path(DATA_DIR) / 'user_settings.json'

def ensure_data_dir():
    """确保数据目录存在"""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

def load_json_file(file_path: Path, default: Dict = None) -> Dict[str, Any]:
    """加载JSON文件，如果不存在则返回默认值"""
    if default is None:
        default = {}

    try:
        ensure_data_dir()

        if not file_path.exists():
            save_json_file(file_path, default)
            return default

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return default

def save_json_file(file_path: Path, data: Dict[str, Any]):
    """保存数据到JSON文件"""
    try:
        ensure_data_dir()

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {file_path}: {e}")

def load_presets() -> Dict[str, Any]:
    """加载用户预设"""
    return load_json_file(PRESETS_FILE)

def save_presets(data: Dict[str, Any]):
    """保存用户预设"""
    save_json_file(PRESETS_FILE, data)

def load_user_settings() -> Dict[str, Any]:
    """加载用户设置"""
    return load_json_file(SETTINGS_FILE)

def save_user_settings(data: Dict[str, Any]):
    """保存用户设置"""
    save_json_file(SETTINGS_FILE, data)
