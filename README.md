# Discord ComfyUI Bot

一个功能强大的 Discord 机器人，用于通过 ComfyUI API 生成图片，支持交互式面板、自定义工作流和预设管理。

## 🎨 功能特性

### 核心功能
- **图片生成** (`/comfy` 命令) - 使用 ComfyUI 工作流生成图片
- **交互式面板** (`/panel` 命令) - 图形化界面配置生成参数
- **预设管理** (`/preset` 命令) - 保存和管理常用提示词组合
- **动态参数获取** - 自动从 ComfyUI 获取可用的采样器和调度器

### 高级特性
- 任务队列系统，防止 API 请求冲突
- 数据持久化存储（用户预设和设置）
- 自定义工作流支持（通过 `workflow.json`）
- 工作流占位符替换系统
- 多种尺寸预设和自定义尺寸
- 自动完成功能

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Discord Bot Token
- 运行中的 ComfyUI 实例

### 本地运行

1. **克隆或创建项目**
```bash
cd comfyui-bot
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置信息
```

必需的环境变量：
```env
DISCORD_TOKEN=your_discord_bot_token_here
COMFYUI_URL=http://localhost:8188
```

4. **配置工作流**

有两种方式配置工作流：

**方式1（推荐）：使用 workflow.json 文件**
- 直接编辑项目目录下的 `workflow.json` 文件
- 默认已包含您提供的工作流模板

**方式2（可选）：通过环境变量**
- 在 `.env` 文件中设置 `WORKFLOW_JSON` 环境变量
- 将完整的工作流 JSON 字符串作为值
- 适合动态部署或需要在不同环境使用不同工作流的场景

工作流中可以使用以下占位符：
- `%width%` - 图片宽度
- `%height%` - 图片高度
- `%prompt%` - 正向提示词
- `%imprompt%` - 负向提示词
- `%seed%` - 随机种子
- `%steps%` - 采样步数
- `%cfg_scale%` - CFG Scale
- `%sampler_name%` - 采样器名称
- `%schedule%` - 调度器名称

5. **运行机器人**
```bash
python main.py
```

### Docker 部署

```bash
# 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 构建镜像
docker build -t comfyui-bot .

# 运行容器
docker run -d \
  --name comfyui-bot \
  --env-file .env \
  --restart unless-stopped \
  comfyui-bot
```

### Zeabur 部署

1. Fork 或上传代码到 GitHub
2. 在 Zeabur 控制台导入项目
3. 配置环境变量：
   - `DISCORD_TOKEN` - Discord 机器人令牌
   - `COMFYUI_URL` - ComfyUI 服务器地址
4. 部署

## 📝 命令使用

### /comfy - 生成图片
```
/comfy prompt:"beautiful anime girl" width:512 height:768
```

可选参数：
- `prompt`: 正向提示词（必需）
- `negative`: 负向提示词
- `width`: 图片宽度
- `height`: 图片高度
- `steps`: 采样步数
- `cfg_scale`: CFG Scale
- `seed`: 随机种子

### /panel - 交互式面板
打开一个图形化界面，通过下拉菜单和按钮配置参数：
- 选择尺寸预设或自定义尺寸
- 选择采样器和调度器（从 ComfyUI 动态获取）
- 配置高级参数（步数、CFG）
- 选择预设提示词
- 保存个人设置

### /preset - 预设管理
```
/preset save name:"my_style" prompt:"masterpiece, best quality" negative:"lowres"
/preset list
/preset delete name:"my_style"
```

### /queue - 查看队列
查看当前任务队列状态和排队情况。

## 🔧 工作流配置

### 工作流结构

`workflow.json` 文件定义了 ComfyUI 的工作流。你可以：

1. 在 ComfyUI 界面中设计工作流
2. 导出工作流 JSON
3. 将需要动态设置的值替换为占位符（如 `%prompt%`）
4. 保存为 `workflow.json`

### 占位符示例

```json
{
  "100": {
    "inputs": {
      "seed": "%seed%",
      "steps": "%steps%",
      "cfg": "%cfg_scale%",
      "sampler_name": "%sampler_name%",
      "scheduler": "%schedule%",
      "denoise": 1
    },
    "class_type": "KSampler"
  }
}
```

### 采样器和调度器

Bot 会在启动时自动从 ComfyUI API 获取可用的采样器和调度器列表，并在面板中显示。不需要硬编码这些选项。

## 📂 项目结构

```
comfyui-bot/
├── main.py                  # 主程序文件
├── comfyui_client.py        # ComfyUI API 客户端
├── workflow_processor.py    # 工作流处理模块
├── utils.py                 # 工具函数（数据持久化）
├── workflow.json            # 工作流配置
├── requirements.txt         # Python 依赖
├── Dockerfile              # Docker 配置
├── .env.example            # 环境变量示例
├── .gitignore             # Git 忽略文件
└── data/                   # 数据存储目录
    ├── user_presets.json   # 用户预设
    └── user_settings.json  # 用户设置
```

## 🛠️ 配置说明

### 环境变量
- `DISCORD_TOKEN`: Discord 机器人令牌（必需）
- `COMFYUI_URL`: ComfyUI 服务器地址（必需，默认: http://localhost:8188）
- `WORKFLOW_JSON`: 工作流 JSON 字符串（可选，如果设置则优先使用，否则使用 workflow.json 文件）
- `DATA_DIR`: 数据存储路径（可选，默认为当前目录）
- `ZEABUR`: 设置为 true 时使用 Zeabur 部署模式

### 数据持久化
- 用户预设和设置保存在 JSON 文件中
- Docker 部署时使用挂载卷保持数据持久化
- Zeabur 部署时自动使用 `/data` 目录

## 📊 ComfyUI API 说明

Bot 使用以下 ComfyUI API 端点：

- `GET /object_info` - 获取节点信息（采样器、调度器等）
- `POST /prompt` - 提交工作流任务
- `GET /history/{prompt_id}` - 获取任务历史
- `GET /view` - 获取生成的图片
- `WebSocket /ws` - 实时监听任务进度

## 🔍 故障排查

### 常见问题

1. **命令不显示**
   - 确保 Bot 有正确的权限
   - 尝试重新邀请 Bot 到服务器

2. **无法连接 ComfyUI**
   - 检查 `COMFYUI_URL` 是否正确
   - 确认 ComfyUI 服务正在运行
   - 检查网络连接和防火墙设置

3. **生成失败**
   - 检查工作流是否正确
   - 查看 ComfyUI 日志了解详细错误
   - 确认所有必需的模型和节点已安装

4. **采样器/调度器列表为空**
   - 确保 ComfyUI 正在运行
   - 检查 ComfyUI 版本是否兼容
   - Bot 会使用默认值作为后备

## 📄 许可证

MIT License

## 🙏 致谢

- ComfyUI 提供的强大图像生成框架
- Discord.py 社区
- 原始 nai-bot 项目提供的架构参考

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

如有问题，请在 GitHub 上提交 Issue。
