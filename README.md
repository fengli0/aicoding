# AI 短剧生成工作台

单机本地 Web 应用，采用"项目 → 分集 → 剧本 → 分镜 → 素材 → 视频 → 音频 → 合成"的阶段式工作流。

## 技术栈

- **前端**: React + TypeScript + Vite
- **后端**: FastAPI + Python
- **数据库**: SQLite
- **媒体处理**: FFmpeg
- **AI 集成**: ComfyUI (图片/视频), LLM, TTS

## 功能特性

### 核心工作流

1. **小说与分集** - 支持粘贴、TXT、MD、DOCX 导入；识别章节，生成分集大纲
2. **剧本编辑器** - 按场次编辑场景、人物、对白、动作
3. **分镜编辑器** - 生成稳定编号的镜头，包含景别、机位、运镜
4. **提示词中心** - 维护人物、场景、道具提示词
5. **素材库** - 生成角色定妆图、场景图和道具图
6. **视频生产台** - 批量视频生成，支持连续性控制
7. **音频工作台** - TTS 配音、BGM、音效配置
8. **合成工作台** - 多轨时间线，输出成片

### 关键特性

- 每个阶段必须人工审核通过后才能进入下一阶段
- 上游修改时，下游结果标记为"已过期"，保留历史版本
- 所有提示词、图片、视频和音频均支持重新生成、版本对比、回退
- 连续镜头使用上一镜头选定版本的末帧
- 失败自动重试 2 次，任意镜头失败不影响已完成镜头

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg
- ComfyUI (可选，用于图片/视频生成)

### 安装后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 安装前端

```bash
cd frontend
npm install
npm run dev
```

### 访问应用

打开浏览器访问 http://localhost:3000

## 项目结构

```
/workspace
├── backend/                 # 后端服务
│   ├── api/                # FastAPI 路由
│   ├── core/               # 核心模块 (数据库、任务队列)
│   ├── models/             # 数据模型
│   ├── services/           # 业务服务 (FFmpeg 等)
│   └── adapters/           # AI 模型适配器
├── frontend/               # 前端应用
│   └── src/
│       ├── api/           # API 客户端
│       ├── components/    # 通用组件
│       ├── pages/         # 页面组件
│       ├── hooks/         # React Hooks
│       ├── store/         # 状态管理
│       ├── types/         # TypeScript 类型
│       └── utils/         # 工具函数
└── shared/                 # 共享代码
    └── types/             # 共享类型定义
```

## API 接口

- `GET /api/projects` - 获取项目列表
- `POST /api/projects` - 创建项目
- `GET /api/projects/{id}` - 获取项目详情
- `DELETE /api/projects/{id}` - 删除项目
- `GET /api/projects/{id}/episodes` - 获取分集列表
- `POST /api/projects/{id}/episodes` - 创建分集
- `GET /api/settings` - 获取设置
- `POST /api/settings` - 更新设置
- `POST /api/settings/test/{adapter}` - 测试连接
- `GET /api/jobs` - 获取任务列表
- `POST /api/jobs/{id}/cancel` - 取消任务
- `GET /api/health` - 健康检查
- `WS /ws` - WebSocket 连接 (任务进度推送)

## 输出规格

默认生成中文横屏短剧：
- 分辨率：1920×1080
- 宽高比：16:9
- 帧率：25fps
- 单集时长：3-8 分钟
- 视频编码：H.264
- 音频编码：AAC 48kHz
- 像素格式：yuv420p

## 许可证

MIT