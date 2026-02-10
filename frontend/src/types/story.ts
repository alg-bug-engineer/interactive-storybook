export interface Character {
  name: string;
  species: string;
  trait: string;
  appearance: string;
}

export interface Setting {
  location: string;
  time: string;
  weather: string;
  visual_description: string;
}

export interface InteractionPoint {
  type: "guess" | "choice" | "name" | "describe";
  prompt: string;
  hints?: string[];
  user_input?: string;
}

export interface StorySegment {
  id?: string;
  text: string;
  scene_description: string;
  emotion: string;
  interaction_point?: InteractionPoint | null;
  image_url?: string | null;
}

export interface StoryState {
  story_id: string;
  title: string;
  theme: string;
  characters: Character[];
  setting: Setting;
  segments?: StorySegment[];
  total_segments: number;
  current_index: number;
  current_segment: StorySegment | null;
  has_interaction: boolean;
  status: "generating" | "narrating" | "waiting_interaction" | "completed";
}
