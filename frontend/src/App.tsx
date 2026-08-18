import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';

// 页面组件（后续实现）
import ProjectCenter from './pages/ProjectCenter';
import Workspace from './pages/Workspace';
import Settings from './pages/Settings';

// 阶段枚举
const PRODUCTION_STAGES = [
  { key: 'novel', label: '小说与分集' },
  { key: 'script', label: '剧本编辑器' },
  { key: 'storyboard', label: '分镜编辑器' },
  { key: 'prompt', label: '提示词中心' },
  { key: 'asset', label: '素材库' },
  { key: 'video', label: '视频生产台' },
  { key: 'audio', label: '音频工作台' },
  { key: 'composite', label: '合成工作台' },
];

function Sidebar() {
  const location = useLocation();
  
  return (
    <div className="sidebar">
      {PRODUCTION_STAGES.map((stage) => (
        <Link
          key={stage.key}
          to={`/workspace/${stage.key}`}
          className={`sidebar-item ${location.pathname.includes(stage.key) ? 'active' : ''}`}
        >
          {stage.label}
        </Link>
      ))}
    </div>
  );
}

function Header({ currentProject }: { currentProject: string | null }) {
  return (
    <header className="header">
      <h1>AI 短剧生成工作台</h1>
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <span>{currentProject || '未选择项目'}</span>
        <Link to="/settings">
          <button className="btn btn-secondary">设置</button>
        </Link>
        <Link to="/">
          <button className="btn btn-secondary">项目中心</button>
        </Link>
      </div>
    </header>
  );
}

function App() {
  const [currentProject, setCurrentProject] = useState<string | null>(null);

  return (
    <BrowserRouter>
      <div className="app-container">
        <Header currentProject={currentProject} />
        <div className="main-content">
          <Sidebar />
          <Routes>
            <Route path="/" element={<ProjectCenter onSelectProject={setCurrentProject} />} />
            <Route path="/workspace/:stage" element={<Workspace projectId={currentProject} />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
