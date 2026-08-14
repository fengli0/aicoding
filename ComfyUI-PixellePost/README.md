# ComfyUI-PixellePost

Pixelle 后期合成 ComfyUI 插件：字幕、分镜片段合成、音画时长对齐、视频拼接和 BGM。

## 功能

- **单镜合成**：图片/视频 + 音频 + 字幕 -> 标准化 MP4 片段
- **音画对齐**：视频短于音频时冻结最后一帧补齐；视频长于音频时裁剪
- **字幕渲染**：ASS 字幕，支持中文字体、描边、阴影、位置和安全边距
- **批量拼接**：按镜头顺序合成多个片段，统一分辨率/FPS，拼接并叠加 BGM
- **断点恢复**：镜头产物和 manifest.json 落盘，同参数再次执行时可复用已完成片段

## 安装

1. 将本插件克隆到 `ComfyUI/custom_nodes/` 目录
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 确保系统已安装 FFmpeg/ffprobe

### 可选依赖

如需 HTML 模板渲染（复杂卡片、网页排版）：
```bash
pip install -e ".[html]"
playwright install
```

## 节点列表

| 节点类 | 分类 | 职责 |
| --- | --- | --- |
| `PixelleCreateShot` | Pixelle/Post | 归一化一个镜头的素材和字幕信息 |
| `PixelleRenderSubtitle` | Pixelle/Post | 生成标题/旁白字幕（ASS 或 PNG） |
| `PixelleComposeScene` | Pixelle/Post | 图像转片段，或视频叠字幕并替换为旁白音频 |
| `PixelleBuildShots` | Pixelle/Batch | 固化顺序、检测缺失素材、分配稳定 job ID |
| `PixelleComposeStoryboard` | Pixelle/Batch | 批量顺序合成镜头 |
| `PixelleConcatVideo` | Pixelle/Batch | 格式归一化、无缝拼接、BGM 混音 |
| `PixelleSaveVideo` | Pixelle/Output | 保存到 ComfyUI output，返回 UI 预览元数据 |

## 系统要求

- Python >= 3.10
- ComfyUI
- FFmpeg/ffprobe（系统级安装）
- Pillow, numpy

## 使用示例

参见 `example_workflows/` 目录中的示例工作流 JSON 文件。

## 许可证

MIT License
