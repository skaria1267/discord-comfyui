# 快速开始指南

## 第一步：准备 Discord Bot

1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 创建新应用 → Bot → 获取 Token
3. 启用以下 Intents：
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
4. 生成邀请链接（需要以下权限）：
   - Send Messages
   - Embed Links
   - Attach Files
   - Use Slash Commands

## 第二步：配置环境

1. 复制环境变量示例文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件：
```env
DISCORD_TOKEN=你的_Discord_Bot_Token
COMFYUI_URL=http://localhost:8188
```

## 第三步：配置工作流

1. 在 ComfyUI 中设计你的工作流
2. 导出工作流为 JSON 格式
3. 将需要动态设置的值替换为占位符：
   - `%width%` - 图片宽度
   - `%height%` - 图片高度
   - `%prompt%` - 正向提示词
   - `%imprompt%` - 负向提示词
   - `%seed%` - 随机种子
   - `%steps%` - 采样步数
   - `%cfg_scale%` - CFG Scale
   - `%sampler_name%` - 采样器
   - `%schedule%` - 调度器

4. 保存为 `workflow.json`

### 示例工作流节点配置：

```json
{
  "100": {
    "inputs": {
      "seed": "%seed%",
      "steps": "%steps%",
      "cfg": "%cfg_scale%",
      "sampler_name": "%sampler_name%",
      "scheduler": "%schedule%"
    },
    "class_type": "KSampler"
  }
}
```

## 第四步：运行 Bot

### 方法 1: 直接运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py

# 或使用启动脚本（推荐）
python start.py
```

### 方法 2: Docker

```bash
# 构建镜像
docker build -t comfyui-bot .

# 运行
docker run -d \
  --name comfyui-bot \
  --env-file .env \
  -v $(pwd)/data:/data \
  --restart unless-stopped \
  comfyui-bot
```

### 方法 3: Docker Compose

```bash
docker-compose up -d
```

## 第五步：测试 Bot

1. 在 Discord 服务器中输入 `/comfy`
2. 填写提示词和参数
3. 等待生成结果

或者使用交互式面板：
1. 输入 `/panel`
2. 通过菜单和按钮配置参数
3. 点击"生成图片"

## 常用命令

### 生成图片
```
/comfy prompt:"a beautiful landscape" width:512 height:768
```

### 打开面板
```
/panel
```

### 保存预设
```
/preset save name:"我的风格" prompt:"masterpiece, best quality" negative:"lowres, bad quality"
```

### 查看队列
```
/queue
```

## 故障排查

### Bot 无法启动
- 检查 `DISCORD_TOKEN` 是否正确
- 查看控制台错误信息

### 无法连接 ComfyUI
- 确认 ComfyUI 正在运行
- 检查 `COMFYUI_URL` 是否正确
- 尝试访问 `http://localhost:8188` 确认 ComfyUI 可访问

### 生成失败
- 查看 ComfyUI 控制台错误
- 确认工作流 JSON 格式正确
- 检查是否所有必需的模型都已安装

### 采样器/调度器列表为空
- 确保 ComfyUI 运行正常
- Bot 会在无法连接时使用默认值

## 高级配置

### 自定义数据目录
```env
DATA_DIR=/path/to/data
```

### 调整队列清理间隔
编辑 `main.py` 中的 `queue_cleanup_task` 函数

### 修改尺寸限制
编辑 `main.py` 中的 `SIZE_LIMITS` 字典

## 下一步

- 探索更多 Discord 命令
- 自定义你的工作流
- 创建和分享预设
- 加入社区讨论

祝你使用愉快！ 🎨
