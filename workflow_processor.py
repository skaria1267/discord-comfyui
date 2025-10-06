# -*- coding: utf-8 -*-
import json
import re
import copy
from typing import Dict, Any, Union

def replace_placeholders(obj: Any, params: Dict[str, Any]) -> Any:
    """
    递归替换对象中的占位符

    Args:
        obj: 要处理的对象（可以是字典、列表、字符串等）
        params: 参数字典

    Returns:
        替换后的对象
    """
    if isinstance(obj, dict):
        # 递归处理字典
        return {key: replace_placeholders(value, params) for key, value in obj.items()}
    elif isinstance(obj, list):
        # 递归处理列表
        return [replace_placeholders(item, params) for item in obj]
    elif isinstance(obj, str):
        # 处理字符串中的占位符
        return replace_string_placeholders(obj, params)
    else:
        # 其他类型直接返回
        return obj

def replace_string_placeholders(text: str, params: Dict[str, Any]) -> Union[str, int, float]:
    """
    替换字符串中的占位符

    Args:
        text: 文本字符串
        params: 参数字典

    Returns:
        替换后的值（可能是字符串或数字）
    """
    # 查找所有 %placeholder% 格式的占位符
    pattern = r'%(\w+)%'
    matches = list(re.finditer(pattern, text))

    if not matches:
        return text

    # 如果整个字符串就是一个占位符，直接返回对应的值（保持类型）
    if len(matches) == 1 and matches[0].group(0) == text:
        placeholder_name = matches[0].group(1)
        if placeholder_name in params:
            return params[placeholder_name]
        else:
            # 占位符不存在，返回原字符串
            return text

    # 如果字符串包含多个占位符或混合文本，进行字符串替换
    result = text
    for match in matches:
        placeholder_name = match.group(1)
        placeholder_full = match.group(0)
        if placeholder_name in params:
            # 转换为字符串进行替换
            result = result.replace(placeholder_full, str(params[placeholder_name]))

    return result

def process_workflow(workflow_template: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理工作流，替换所有占位符

    Args:
        workflow_template: 工作流模板
        params: 参数字典

    Returns:
        处理后的工作流
    """
    # 深拷贝模板，避免修改原始数据
    workflow = copy.deepcopy(workflow_template)

    # 替换所有占位符
    workflow = replace_placeholders(workflow, params)

    return workflow

def load_workflow(workflow_path: str) -> Dict[str, Any]:
    """
    从文件加载工作流

    Args:
        workflow_path: 工作流文件路径

    Returns:
        工作流字典
    """
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    return workflow

def validate_workflow_params(workflow: Dict[str, Any]) -> list[str]:
    """
    验证工作流中的所有占位符

    Args:
        workflow: 工作流字典

    Returns:
        占位符列表
    """
    placeholders = set()

    def find_placeholders(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                find_placeholders(value)
        elif isinstance(obj, list):
            for item in obj:
                find_placeholders(item)
        elif isinstance(obj, str):
            pattern = r'%(\w+)%'
            matches = re.findall(pattern, obj)
            placeholders.update(matches)

    find_placeholders(workflow)
    return sorted(list(placeholders))

# 示例使用
if __name__ == '__main__':
    # 测试工作流处理
    workflow = load_workflow('workflow.json')

    # 查找所有占位符
    placeholders = validate_workflow_params(workflow)
    print(f"Found placeholders: {placeholders}")

    # 替换参数
    params = {
        'width': 512,
        'height': 768,
        'prompt': 'a beautiful anime girl',
        'imprompt': 'lowres, bad quality',
        'seed': 123456,
        'steps': 20,
        'cfg_scale': 7.0,
        'sampler_name': 'euler_ancestral',
        'schedule': 'normal'
    }

    processed = process_workflow(workflow, params)
    print(json.dumps(processed, indent=2, ensure_ascii=False))
