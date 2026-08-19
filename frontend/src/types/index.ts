export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  status: StageStatus;
  episode_count: number;
  current_episode: number;
  production_stage: string;
  task_progress: number;
  disk_usage_mb: number;
  last_error?: string;
  settings: Record<string, any>;
  resolution_width: number;
  resolution_height: number;
  aspect_ratio: string;
  fps: number;
  target_duration_min: number;
  target_duration_max: number;
}

export interface Episode {
  id: string;
  project_id: string;
  episode_number: number;
  title: string;
  summary: string;
  core_conflict: string;
  status: StageStatus;
  script_status: StageStatus;
  storyboard_status: StageStatus;
  asset_status: StageStatus;
  video_status: StageStatus;
  audio_status: StageStatus;
  composite_status: StageStatus;
  created_at: string;
  updated_at: string;
}

export type StageStatus = 
  | 'draft'
  | 'pending_review'
  | 'approved'
  | 'generating'
  | 'completed'
  | 'failed'
  | 'expired';

export interface ScriptScene {
  id: string;
  episode_id: string;
  scene_number: number;
  location: string;
  time_of_day: string;
  interior_exterior: string;
  characters: string[];
  costumes: Record<string, string>;
  props: string[];
  actions: string;
  dialogues: Array<{ character: string; text: string; emotion?: string; duration?: number }>;
  narration: string;
  audio_requirements: string[];
  status: StageStatus;
  created_at: string;
  updated_at: string;
}

export interface Shot {
  id: string;
  scene_id: string;
  shot_number: number;
  shot_size: string;
  camera_position: string;
  camera_movement: string;
  action: string;
  dialogue: string;
  narration: string;
  estimated_duration: number;
  frame_start_state: string;
  frame_end_state: string;
  continuity_source: string;
  continuity_ref_shot_id?: string;
  edit_transition: string;
  transition_duration: number;
  characters: string[];
  scene_ref?: string;
  prop_refs: string[];
  status: StageStatus;
  created_at: string;
  updated_at: string;
}

export interface AssetVersion {
  id: string;
  asset_type: 'image' | 'video' | 'audio';
  entity_id?: string;
  shot_id?: string;
  version_number: number;
  file_path: string;
  thumbnail_path: string;
  model_name: string;
  workflow_version: string;
  parameters: Record<string, any>;
  seed?: number;
  input_assets: string[];
  dependency_versions: string[];
  status: StageStatus;
  error_message?: string;
  width: number;
  height: number;
  duration: number;
  fps: number;
  created_at: string;
  is_current: boolean;
}

export interface GenerationJob {
  id: string;
  job_type: string;
  priority: number;
  project_id: string;
  episode_id?: string;
  shot_id?: string;
  asset_id?: string;
  parameters: Record<string, any>;
  workflow_json?: string;
  status: StageStatus;
  progress: number;
  error_message?: string;
  retry_count: number;
  max_retries: number;
  comfyui_job_id?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface PromptBundle {
  id: string;
  project_id: string;
  type: 'character' | 'scene' | 'prop' | 'shot';
  entity_id?: string;
  positive_prompt: string;
  negative_prompt: string;
  model_params: Record<string, any>;
  seed?: number;
  locked: boolean;
  current_version_id?: string;
  created_at: string;
  updated_at: string;
}

export interface EntityProfile {
  id: string;
  project_id: string;
  name: string;
  type: 'character' | 'location' | 'prop';
  description: string;
  aliases: string[];
  image_url?: string;
  prompt_bundle_id?: string;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EntityVariant {
  id: string;
  entity_id: string;
  name: string;
  variant_type: 'costume' | 'age' | 'injury' | 'time_of_day' | 'weather';
  description?: string;
  image_url?: string;
  prompt_bundle_id?: string;
  is_active: boolean;
  created_at: string;
}

export interface VideoVersion {
  id: string;
  shot_id: string;
  version_number: number;
  file_path: string;
  thumbnail_path: string;
  width: number;
  height: number;
  duration: number;
  fps: number;
  file_size: number;
  model_name: string;
  workflow_version: string;
  prompt_used: string;
  seed?: number;
  continuity_frame_path?: string;
  reference_image_path?: string;
  error_message?: string;
  is_current: boolean;
  comfyui_job_id?: string;
  created_at: string;
}

export interface AudioTrack {
  id: string;
  episode_id: string;
  type: 'dialogue' | 'narration' | 'bgm' | 'sfx';
  character_id?: string;
  file_path: string;
  start_time: number;
  duration: number;
  volume: number;
  fade_in?: number;
  fade_out?: number;
  metadata: Record<string, any>;
}

export interface SubtitleCue {
  id: string;
  episode_id: string;
  start_time: number;
  end_time: number;
  text: string;
  character_name?: string;
}

export interface ExportJob {
  id: string;
  project_id: string;
  episode_id?: string;
  type: 'episode' | 'full_series';
  format: 'mp4' | 'mov' | 'mkv';
  include_subtitles: boolean;
  output_path?: string;
  status: StageStatus;
  progress: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface TaskQueueItem {
  id: string;
  type: 'llm' | 'image_gen' | 'video_gen' | 'tts' | 'ffmpeg' | 'export';
  status: 'pending' | 'running' | 'completed' | 'failed';
  priority: number;
  retry_count: number;
  data: Record<string, any>;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface WebSocketMessage {
  type: 'job_progress' | 'job_completed' | 'job_failed' | 'queue_update' | 'error';
  payload: any;
  timestamp: string;
}

export interface ComfyUIConfig {
  enabled: boolean;
  base_url: string;
  workflow_path: string;
  api_key?: string;
  timeout: number;
  max_retries: number;
}

export interface TTSConfig {
  provider: 'edge' | 'azure' | 'mock';
  api_key?: string;
  region?: string;
  default_voice: string;
  default_speed: number;
}

export interface LLMConfig {
  provider: 'openai' | 'anthropic' | 'local';
  base_url?: string;
  api_key?: string;
  model: string;
  max_tokens: number;
  temperature: number;
}
