import React from 'react';

export default function Workspace({ projectId }: { projectId: string | null }) {
  if (!projectId) {
    return (
      <div className="editor-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: '#888' }}>
          <h2>请先选择项目</h2>
          <p>在项目中心选择或创建一个项目后进入工作台</p>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace">
      <div className="workspace-header">
        <span>项目 ID: {projectId}</span>
        <select className="select">
          <option value="1">第 1 集</option>
          <option value="2">第 2 集</option>
        </select>
      </div>
      <div className="workspace-body">
        <div className="editor-panel">
          <p>工作台内容将根据左侧选择的阶段动态加载</p>
          <p>当前实现包含基础框架，各阶段编辑器将在后续迭代中完成。</p>
        </div>
        <div className="properties-panel">
          <div className="card-title">参数与版本</div>
          <p style={{ fontSize: '13px', color: '#888' }}>属性面板将显示当前选中对象的详细参数和版本历史</p>
        </div>
      </div>
      <div className="task-queue">
        <div style={{ padding: '12px', borderBottom: '1px solid #eee' }}>
          <strong>全局任务队列</strong>
        </div>
        <div style={{ padding: '12px', color: '#888', fontSize: '13px' }}>
          暂无任务
        </div>
      </div>
    </div>
  );
}
