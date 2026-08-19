# AI 短剧生成工作台

单机本地 Web 应用，采用"项目 → 分集 → 剧本 → 分镜 → 素材 → 视频 → 音频 → 合成"的阶段式工作流。

## 技术栈

- **前端**: React + TypeScript + Vite + Zustand + TanStack Query
- **后端**: FastAPI + Python + SQLAlchemy + SQLite
- **媒体处理**: FFmpeg
- **AI 集成**: ComfyUI (Minimax H3), LLM, TTS

## 功能特性

- 小说导入与分集规划（支持 TXT, MD, DOCX）
- 结构化剧本编辑器
- 分镜编辑器与提示词生成
- 素材库与版本管理
- 视频生成与连续性处理
- 音频工作台（TTS、BGM、音效）
- 多轨时间线与合成导出

## 快速启动

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 安装后端依赖
pip install -r backend/requirements.txt

# 安装前端依赖
cd frontend
npm install
```

### 2. 一键启动

双击 `start.bat` (Windows) 或执行:

```bash
./start.sh  # Linux/Mac
```

服务地址:
- 前端: http://127.0.0.1:5173
- 后端 API: http://127.0.0.1:8000
- API 文档: http://127.0.0.1:8000/docs

## 项目结构

```
/workspace
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── core/         # 配置
│   │   ├── db/           # 数据库
│   │   ├── models/       # 数据模型
│   │   ├── services/     # 业务服务
│   │   ├── utils/        # 工具函数
│   │   └── main.py       # 应用入口
│   ├── projects/         # 项目数据
│   └── uploads/          # 上传文件
├── frontend/
│   ├── src/
│   │   ├── api/          # API 客户端
│   │   ├── components/   # React 组件
│   │   ├── hooks/        # 自定义 Hooks
│   │   ├── pages/        # 页面组件
│   │   ├── store/        # 状态管理
│   │   ├── types/        # TypeScript 类型
│   │   └── App.tsx       # 应用入口
│   └── package.json
├── start.bat             # Windows 启动脚本
└── README.md
```

## API 端点

- `GET /api/projects` - 获取项目列表
- `POST /api/projects` - 创建项目
- `GET /api/projects/{id}/episodes` - 获取分集列表
- `POST /api/novel/import` - 导入小说
- `GET /api/episodes/{id}/scenes` - 获取场景列表
- `POST /api/scenes/{id}/generate-shots` - 生成分镜
- `GET /api/jobs` - 获取任务队列
- `POST /api/jobs` - 创建生成任务

## 配置

在设置页面配置:
- ComfyUI 服务地址
- LLM 服务地址
- TTS 服务地址
- FFmpeg 路径

## 输出规格

- 分辨率：1920×1080
- 宽高比：16:9
- 帧率：25fps
- 单集时长：3-8 分钟
- 视频编码：H.264
- 音频编码：AAC 48kHz
- 像素格式：yuv420p

## 注意事项

- 首版为 Windows 单用户中文工具
- 所有项目素材保存在本地
- 需要 ComfyUI 服务运行在 8188 端口
- FFmpeg 需要预先安装并加入 PATH
