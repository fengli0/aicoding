// React hooks for data fetching and mutations
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi, episodesApi, scenesApi, shotsApi, jobsApi, novelApi } from '../api';

// Projects
export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list(),
  });
}

export function useProject(id: number | null) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => projectsApi.get(id!),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) => 
      projectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

// Episodes
export function useEpisodes(projectId: number | null) {
  return useQuery({
    queryKey: ['episodes', projectId],
    queryFn: () => episodesApi.list(projectId!),
    enabled: !!projectId,
  });
}

// Novel Import
export function useImportNovel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: novelApi.import,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['episodes'] });
      queryClient.invalidateQueries({ queryKey: ['entities'] });
    },
  });
}

// Scenes
export function useScenes(episodeId: number | null) {
  return useQuery({
    queryKey: ['scenes', episodeId],
    queryFn: () => scenesApi.list(episodeId!),
    enabled: !!episodeId,
  });
}

export function useGenerateShots() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sceneId: number) => shotsApi.generateFromScene(sceneId),
    onSuccess: (_, sceneId) => {
      queryClient.invalidateQueries({ queryKey: ['shots', sceneId] });
    },
  });
}

// Shots
export function useShots(sceneId: number | null) {
  return useQuery({
    queryKey: ['shots', sceneId],
    queryFn: () => shotsApi.list(sceneId!),
    enabled: !!sceneId,
  });
}

// Jobs
export function useJobs(status?: string) {
  return useQuery({
    queryKey: ['jobs', status],
    queryFn: () => jobsApi.list(status),
    refetchInterval: 2000, // Poll every 2 seconds
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: number) => jobsApi.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: jobsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}
