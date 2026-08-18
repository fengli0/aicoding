import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { settingsApi } from '../api';

export default function Settings() {
  const { data: settingsData, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const res = await settingsApi.get();
      return res.data;
    },
  });

  const [form, setForm] = useState({
    llm_url: '',
    llm_api_key: '',
    llm_model: '',
    image_url: '',
    image_model: '',
    video_url: '',
    video_model: 'minimax-h3',
    tts_url: '',
    tts_api_key: '',
    tts_voice: '',
    ffmpeg_path: 'ffmpeg',
    ffprobe_path: 'ffprobe',
  });

  const [testingAdapter, setTestingAdapter] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, boolean>>({});
  const initializedRef = useRef(false);

  // 加载现有设置到表单（仅执行一次）
  useEffect(() => {
    if (settingsData && !initializedRef.current) {
      initializedRef.current = true;
      setForm(prev => ({
        ...prev,
        llm_url: settingsData.llm?.url || '',
        llm_model: settingsData.llm?.model || '',
        image_url: settingsData.image?.url || '',
        image_model: settingsData.image?.model || '',
        video_url: settingsData.video?.url || '',
        video_model: settingsData.video?.model || 'minimax-h3',
        tts_url: settingsData.tts?.url || '',
        tts_voice: settingsData.tts?.voice || '',
        ffmpeg_path: settingsData.ffmpeg || 'ffmpeg',
      }));
    }
  }, [settingsData]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await settingsApi.update(data);
      return res.data;
    },
  });

  const testMutation = useMutation({
    mutationFn: async (adapterType: string) => {
      setTestingAdapter(adapterType);
      try {
        const res = await settingsApi.test(adapterType);
        setTestResults(prev => ({ ...prev, [adapterType]: res.data.success }));
        return res.data.success;
      } finally {
        setTestingAdapter(null);
      }
    },
  });

  if (isLoading) {
    return <div className="editor-panel">加载中...</div>;
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate(form);
  };

  return (
    <div className="editor-panel">
      <h2>系统设置</h2>
      
      <form onSubmit={handleSubmit} style={{ maxWidth: '600px' }}>
        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-title">LLM 配置</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>服务地址</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="http://localhost:11434/v1"
                value={form.llm_url}
                onChange={(e) => setForm({ ...form, llm_url: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>API Key</label>
              <input
                className="input"
                style={{ width: '100%' }}
                type="password"
                placeholder="可选"
                value={form.llm_api_key}
                onChange={(e) => setForm({ ...form, llm_api_key: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>模型名称</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="qwen2.5:7b"
                value={form.llm_model}
                onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => testMutation.mutate('llm')}
              disabled={testingAdapter === 'llm'}
            >
              {testingAdapter === 'llm' ? '测试中...' : '测试连接'}
            </button>
            {testResults.llm !== undefined && (
              <span style={{ color: testResults.llm ? 'green' : 'red' }}>
                {testResults.llm ? '✓ 连接成功' : '✗ 连接失败'}
              </span>
            )}
          </div>
        </div>

        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-title">图片生成配置 (ComfyUI)</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>ComfyUI 地址</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="http://localhost:8188"
                value={form.image_url}
                onChange={(e) => setForm({ ...form, image_url: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>模型名称</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="sd_xl_base_1.0.safetensors"
                value={form.image_model}
                onChange={(e) => setForm({ ...form, image_model: e.target.value })}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => testMutation.mutate('image')}
              disabled={testingAdapter === 'image'}
            >
              {testingAdapter === 'image' ? '测试中...' : '测试连接'}
            </button>
            {testResults.image !== undefined && (
              <span style={{ color: testResults.image ? 'green' : 'red' }}>
                {testResults.image ? '✓ 连接成功' : '✗ 连接失败'}
              </span>
            )}
          </div>
        </div>

        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-title">视频生成配置 (ComfyUI Minimax H3)</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>ComfyUI 地址</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="http://localhost:8188"
                value={form.video_url}
                onChange={(e) => setForm({ ...form, video_url: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>模型名称</label>
              <input
                className="input"
                style={{ width: '100%' }}
                value={form.video_model}
                onChange={(e) => setForm({ ...form, video_model: e.target.value })}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => testMutation.mutate('video')}
              disabled={testingAdapter === 'video'}
            >
              {testingAdapter === 'video' ? '测试中...' : '测试连接'}
            </button>
            {testResults.video !== undefined && (
              <span style={{ color: testResults.video ? 'green' : 'red' }}>
                {testResults.video ? '✓ 连接成功' : '✗ 连接失败'}
              </span>
            )}
          </div>
        </div>

        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-title">TTS 配置</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>服务地址</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="http://localhost:5000"
                value={form.tts_url}
                onChange={(e) => setForm({ ...form, tts_url: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>API Key</label>
              <input
                className="input"
                style={{ width: '100%' }}
                type="password"
                value={form.tts_api_key}
                onChange={(e) => setForm({ ...form, tts_api_key: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>默认音色</label>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="zh_female"
                value={form.tts_voice}
                onChange={(e) => setForm({ ...form, tts_voice: e.target.value })}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => testMutation.mutate('tts')}
              disabled={testingAdapter === 'tts'}
            >
              {testingAdapter === 'tts' ? '测试中...' : '测试连接'}
            </button>
            {testResults.tts !== undefined && (
              <span style={{ color: testResults.tts ? 'green' : 'red' }}>
                {testResults.tts ? '✓ 连接成功' : '✗ 连接失败'}
              </span>
            )}
          </div>
        </div>

        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-title">FFmpeg 配置</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>FFmpeg 路径</label>
              <input
                className="input"
                style={{ width: '100%' }}
                value={form.ffmpeg_path}
                onChange={(e) => setForm({ ...form, ffmpeg_path: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '4px', fontSize: '13px' }}>FFprobe 路径</label>
              <input
                className="input"
                style={{ width: '100%' }}
                value={form.ffprobe_path}
                onChange={(e) => setForm({ ...form, ffprobe_path: e.target.value })}
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? '保存中...' : '保存设置'}
        </button>
      </form>
    </div>
  );
}
