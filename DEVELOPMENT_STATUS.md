# AI 短剧生成工作台 - 开发进度报告

## 已完成的核心功能

### 1. 后端架构 (FastAPI + Python)

#### 数据库模型 (`backend/app/models/schemas.py`)
- ✅ Project - 项目管理
- ✅ Episode - 分集管理
- ✅ EntityProfile - 实体档案（人物、场景、道具）
- ✅ EntityVariant - 实体变体（服装、伤势、昼夜等）
- ✅ ScriptScene - 剧本场次
- ✅ Shot - 分镜头
- ✅ PromptBundle - 提示词包
- ✅ AssetVersion - 素材版本（图片/视频/音频）
- ✅ GenerationJob - 生成任务
- ✅ TimelineClip - 时间线片段
- ✅ ExportJob - 导出任务

#### 核心服务
- ✅ `LLMService` - 小说解析、分集规划、提示词生成
- ✅ `ComfyUIService` - 视频/图片生成工作流提交与监控
- ✅ `TTSService` - 语音合成（新增）
- ✅ `FFmpegService` - 视频处理、音频混合、最终合成（新增）
- ✅ `ContinuityService` - 画面连续性管理（新增）
- ✅ `TaskQueue` - 持久化任务队列，支持重启恢复

#### API 路由 (`backend/app/api/routes.py`)
- ✅ 项目管理（CRUD）
- ✅ 分集管理
- ✅ 小说导入（TXT/MD/DOCX → 分集规划 + 实体提取）
- ✅ 剧本编辑（场次管理）
- ✅ 分镜生成与管理
- ✅ 连续性检查与过期标记
- ✅ TTS 语音生成
- ✅ 字幕生成（SRT）
- ✅ 视频导出与规格验证

### 2. 前端架构 (React + TypeScript)

#### 基础结构
- ✅ Vite + React + TypeScript 项目配置
- ✅ 类型定义 (`frontend/src/types/index.ts`)
- ✅ API 客户端 (`frontend/src/api/index.ts`)
- ✅ 状态管理 (`frontend/src/store/appStore.ts`)
- ✅ 自定义 Hooks (`frontend/src/hooks/useQueries.ts`)

#### 页面组件
- ✅ `ProjectCenter.tsx` - 项目中心
- ✅ `Workspace.tsx` - 项目工作台
- ✅ `Settings.tsx` - 设置页

### 3. 关键特性实现

#### 连续性管理 (`ContinuityService`)
- ✅ 自动判断是否继承上一镜头末帧
- ✅ 场景/时间变化时不继承
- ✅ 硬切/淡入淡出不继承
- ✅ 上游版本变更时自动标记下游过期
- ✅ 连续性链验证

#### 视频导出规范
- ✅ 分辨率：1920×1080
- ✅ 帧率：25fps
- ✅ 像素格式：yuv420p
- ✅ 视频编码：H.264
- ✅ 音频编码：AAC 48kHz
- ✅ 输出格式：MP4 + SRT

#### 任务队列
- ✅ 异步任务处理
- ✅ 失败自动重试（默认 2 次）
- ✅ 并发控制（视频生成默认并发 1）
- ✅ 重启后恢复未完成任务

### 4. 配置文件

#### 后端配置 (`backend/app/core/config.py`)
```python
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 25
MIN_EPISODE_DURATION = 180  # 3 分钟
MAX_EPISODE_DURATION = 480  # 8 分钟
MAX_CONCURRENT_VIDEO_JOBS = 1
VIDEO_RETRY_COUNT = 2
COMFYUI_URL = "http://127.0.0.1:8188"
```

### 5. 启动脚本

- ✅ `start.bat` - Windows 一键启动
- ✅ `start.sh` - Linux/Mac启动脚本

## 待完成功能

### 高优先级
1. **ComfyUI 工作流模板**
   - Minimax H3 视频生成工作流 JSON
   - 节点映射配置
   - 参考图片上传处理

2. **前端完整页面**
   - 小说导入与分集编辑器
   - 剧本编辑器（表格/剧本格式切换）
   - 分镜编辑器（拖动排序、批量修改）
   - 素材库（多候选对比、版本管理）
   - 视频生产台（批量生成、进度监控）
   - 音频工作台（音色绑定、情绪调节）
   - 合成时间线（多轨预览）

3. **TTS 集成**
   - 实际 TTS 服务对接（Edge TTS / Azure TTS / 本地模型）
   - 音色库管理
   - 对白时长与镜头时长匹配检查

4. **完整性检查**
   - 上游修改→下游过期联动测试
   - 连续镜头串行生成逻辑
   - 版本回退与对比 UI

### 中优先级
1. **错误处理与恢复**
   - ComfyUI 离线/超时处理
   - 磁盘空间检查
   - OOM 检测与恢复

2. **性能优化**
   - 大文件分块上传
   - 缩略图生成缓存
   - 数据库查询优化

3. **用户体验**
   - WebSocket 实时进度推送
   - 操作撤销/重做
   - 快捷键支持

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite |
| 后端 | FastAPI + Python 3.12 |
| 数据库 | SQLite |
| 媒体处理 | FFmpeg |
| AI 生成 | ComfyUI (可插拔) |
| 任务队列 | asyncio.Queue |
| 实时通信 | WebSocket |

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 2. 安装依赖
cd backend
pip install -r requirements.txt

# 3. 安装前端依赖
cd ../frontend
npm install

# 4. 一键启动
# Windows: 双击 start.bat
# Linux/Mac: ./start.sh
```

## API 端点概览

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/projects | 创建项目 |
| GET | /api/projects | 项目列表 |
| POST | /api/novel/import | 导入小说 |
| GET | /api/projects/{id}/episodes | 获取分集 |
| POST | /api/scenes | 创建场次 |
| POST | /api/scenes/{id}/generate-shots | AI 生成分镜 |
| GET | /api/shots/{id}/continuity | 检查连续性 |
| POST | /api/audio/generate-dialogue | 生成对白音频 |
| POST | /api/audio/generate-subtitles | 生成字幕 |
| POST | /api/export/episode/{id} | 导出成片 |
| GET | /api/export/verify/{job_id} | 验证导出规格 |

## 下一步行动

1. **完善 ComfyUI 工作流集成** - 提供示例 workflow JSON
2. **开发前端编辑器组件** - 按阶段逐个完成
3. **端到端测试** - 使用 30-100 个镜头完成全流程验证
4. **安装打包** - 制作独立启动器

---
*最后更新：2025-01-XX*
*版本：v1.0.0-alpha*
