import axios from 'axios';
import type { Project, Episode, GenerationJob } from '../types';

const api = axios.create({
  baseURL: '/api',
});

export const projectApi = {
  list: () => api.get<{ projects: Project[] }>('/projects'),
  create: (data: { name: string; description?: string }) => api.post('/projects', data),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  delete: (id: string) => api.delete(`/projects/${id}`),
};

export const episodeApi = {
  list: (projectId: string) => api.get<{ episodes: Episode[] }>(`/projects/${projectId}/episodes`),
  create: (projectId: string, data: { episode_number: number; title?: string; summary?: string }) =>
    api.post(`/projects/${projectId}/episodes`, data),
};

export const jobApi = {
  list: (projectId?: string) => api.get<{ jobs: GenerationJob[] }>('/jobs', { params: { project_id: projectId } }),
  cancel: (jobId: string) => api.post(`/jobs/${jobId}/cancel`),
};

export const settingsApi = {
  get: () => api.get('/settings'),
  update: (settings: any) => api.post('/settings', settings),
  test: (adapterType: string) => api.post(`/settings/test/${adapterType}`),
};

export const healthApi = {
  check: () => api.get('/health'),
};