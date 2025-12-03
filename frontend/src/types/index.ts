export interface User {
  id: string;  // Database UUID - used for API calls
  keycloak_id: string;  // Keycloak ID - used for WebSocket online status
  username: string;
  email: string;
  display_name?: string;
  avatar_url?: string;
  phone_number?: string;
  status_text?: string;
  status: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED';
  role: 'ADMIN' | 'MODERATOR' | 'MEMBER';
}

export interface Channel {
  id: string;
  name: string;
  description?: string;
  channel_type: 'PUBLIC' | 'PRIVATE' | 'DIRECT';
  topic?: string;
  created_at: string;
  updated_at: string;
  member_count?: number;
  unread_count?: number;
}

export interface Message {
  id: string;
  channel_id: string;
  author_id: string;
  author?: User;
  author_username?: string;
  author_display_name?: string;
  author_avatar_url?: string;
  content: string;
  thread_id?: string;
  parent_message_id?: string;
  message_type: 'text' | 'file' | 'system';
  is_edited: boolean;
  created_at: string;
  updated_at: string;
  reply_count?: number;
  reactions?: ReactionSummary[];
  attachments?: FileUpload[];
}

export interface Thread {
  id: string;
  channel_id: string;
  root_message_id: string;
  participant_count: number;
  reply_count: number;
  last_reply_at?: string;
  created_at: string;
}

export interface Reaction {
  id: string;
  message_id: string;
  user_id: string;
  emoji: string;
  created_at: string;
}

export interface ReactionSummary {
  emoji: string;
  count: number;
  users: { id: string; username: string }[];
  user_reacted: boolean;
}

export interface FileUpload {
  id: string;
  original_filename: string;
  storage_path: string;
  file_url: string;
  thumbnail_url?: string;
  size_bytes: number;
  mime_type: string;
  uploaded_by_id: string;
  channel_id?: string;
  message_id?: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}
