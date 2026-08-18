import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectApi, healthApi } from '../api';
import type { Project } from '../types';

interface Props {
  onSelectProject: (projectId: string) => void;
}

export default function ProjectCenter({ onSelectProject }: Props) {
  const navigate = useNavigate();
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const queryClient = useQueryClient();

  const { data: projectsData, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await projectApi.list();
      return res.data.projects;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: { name: string; description?: string }) => {
      const res = await projectApi.create(data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setShowNewProject(false);
      setNewProjectName('');
      setNewProjectDesc('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await projectApi.delete(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await healthApi.check();
      return res.data;
    },
    refetchInterval: 5000,
  });

  const handleCreateProject = () => {
    if (!newProjectName.trim()) return;
    createMutation.mutate({ name: newProjectName, description: newProjectDesc });
  };

  const getStatusBadgeClass = (status: string) => {
    return `status-badge status-${status}`;
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      draft: '草稿',
      pending_review: '待审核',
      approved: '已通过',
      generating: '生成中',
      completed: '已完成',
      failed: '失败',
      expired: '已过期',
    };
    return labels[status] || status;
  };

  if (isLoading) {
    return <div className="editor-panel">加载中...</div>;
  }

  return (
    <div className="editor-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>项目中心</h2>
        <button className="btn btn-primary" onClick={() => setShowNewProject(true)}>
          + 新建项目
        </button>
      </div>

      {healthData && (
        <div className="card" style={{ marginBottom: '20px', padding: '12px' }}>
          <strong>系统状态:</strong>{' '}
          {healthData.status === 'ok' ? (
            <span style={{ color: 'green' }}>正常</span>
          ) : (
            <span style={{ color: 'red' }}>异常</span>
          )}
          {' | '}
          数据库：{healthData.database ? '✓' : '✗'}
          {' | '}
          任务队列：{healthData.task_queue ? '✓' : '✗'}
          {' | '}
          FFmpeg: {healthData.ffmpeg ? '✓' : '✗'}
        </div>
      )}

      {showNewProject && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-title">新建项目</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input
              className="input"
              placeholder="项目名称"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
            />
            <input
              className="input"
              placeholder="项目描述（可选）"
              value={newProjectDesc}
              onChange={(e) => setNewProjectDesc(e.target.value)}
            />
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-primary" onClick={handleCreateProject}>
                创建
              </button>
              <button className="btn btn-secondary" onClick={() => setShowNewProject(false)}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
        {projectsData?.map((project) => (
          <div key={project.id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <h3 style={{ margin: '0 0 8px 0' }}>{project.name}</h3>
              <span className={getStatusBadgeClass(project.status)}>{getStatusLabel(project.status)}</span>
            </div>
            <p style={{ color: '#666', fontSize: '14px', margin: '8px 0' }}>{project.description || '无描述'}</p>
            <div style={{ fontSize: '13px', color: '#888' }}>
              <div>集数：{project.episode_count}</div>
              <div>阶段：{project.production_stage}</div>
              <div>进度：{(project.task_progress * 100).toFixed(1)}%</div>
              <div>磁盘：{project.disk_usage_mb.toFixed(1)} MB</div>
              <div>规格：{project.resolution_width}x{project.resolution_height} @ {project.fps}fps</div>
            </div>
            {project.last_error && (
              <div style={{ color: 'red', fontSize: '12px', marginTop: '8px' }}>错误：{project.last_error}</div>
            )}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                onClick={() => {
                  onSelectProject(project.id);
                  navigate('/workspace/novel');
                }}
              >
                进入工作台
              </button>
              <button
                className="btn btn-danger"
                onClick={() => {
                  if (confirm(`确定删除项目 "${project.name}"？`)) {
                    deleteMutation.mutate(project.id);
                  }
                }}
              >
                删除
              </button>
            </div>
          </div>
        ))}

        {projectsData?.length === 0 && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: '#888' }}>
            暂无项目，点击右上角创建新项目
          </div>
        )}
      </div>
    </div>
  );
}
