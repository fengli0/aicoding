// Zustand store for application state
import { create } from 'zustand';
import type { Project, Episode, Shot, GenerationJob, StageStatus } from '../types';

interface AppState {
  // Current selection
  currentProjectId: number | null;
  currentEpisodeId: number | null;
  currentStage: string;
  
  // Data caches
  projects: Project[];
  episodes: Episode[];
  shots: Shot[];
  jobs: GenerationJob[];
  
  // UI state
  isLoading: boolean;
  error: string | null;
  wsConnected: boolean;
  
  // Actions
  setCurrentProject: (id: number | null) => void;
  setCurrentEpisode: (id: number | null) => void;
  setCurrentStage: (stage: string) => void;
  setProjects: (projects: Project[]) => void;
  setEpisodes: (episodes: Episode[]) => void;
  setShots: (shots: Shot[]) => void;
  setJobs: (jobs: GenerationJob[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setWsConnected: (connected: boolean) => void;
  
  // Helper to update item status
  updateItemStatus: (type: 'project' | 'episode' | 'shot', id: number, status: StageStatus) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  currentProjectId: null,
  currentEpisodeId: null,
  currentStage: 'project',
  projects: [],
  episodes: [],
  shots: [],
  jobs: [],
  isLoading: false,
  error: null,
  wsConnected: false,
  
  // Actions
  setCurrentProject: (id) => set({ currentProjectId: id }),
  setCurrentEpisode: (id) => set({ currentEpisodeId: id }),
  setCurrentStage: (stage) => set({ currentStage: stage }),
  setProjects: (projects) => set({ projects }),
  setEpisodes: (episodes) => set({ episodes }),
  setShots: (shots) => set({ shots }),
  setJobs: (jobs) => set({ jobs }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setWsConnected: (connected) => set({ wsConnected: connected }),
  
  updateItemStatus: (type, id, status) => set((state) => {
    if (type === 'project') {
      return {
        projects: state.projects.map(p => 
          p.id === id ? { ...p, status } : p
        )
      };
    }
    if (type === 'episode') {
      return {
        episodes: state.episodes.map(e => 
          e.id === id ? { ...e, status } : e
        )
      };
    }
    if (type === 'shot') {
      return {
        shots: state.shots.map(s => 
          s.id === id ? { ...s, status } : s
        )
      };
    }
    return state;
  }),
}));
