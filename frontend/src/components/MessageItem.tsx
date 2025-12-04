'use client';

import { useState, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Message } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import { Smile, MessageSquare, MoreVertical, File, Download, FileText, FileImage, FileVideo, Trash2 } from 'lucide-react';
import { messageApi, filesApi } from '@/lib/api';
import { AuthService } from '@/lib/auth';
import { useAuthStore } from '@/store/authStore';
import { config } from '@/lib/config';
import { UserProfilePopup } from './UserProfilePopup';

interface MessageItemProps {
  message: Message;
  showAvatar: boolean;
  onReplyClick?: (message: Message) => void;
  highlightText?: string;
}

export function MessageItem({ message, showAvatar, onReplyClick, highlightText }: MessageItemProps) {
  const [showActions, setShowActions] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showUserProfile, setShowUserProfile] = useState(false);
  const [profilePosition, setProfilePosition] = useState({ x: 0, y: 0 });
  const nameRef = useRef<HTMLSpanElement>(null);
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  // Common emojis for quick reactions
  const quickEmojis = ['👍', '❤️', '😂', '🎉', '👀', '🔥'];

  // Check if current user can delete this message
  const canDelete = user?.id === message.author_id || user?.id === message.author?.id;

  const addReactionMutation = useMutation({
    mutationFn: async (emoji: string) => {
      return await messageApi.post(`/messages/${message.id}/reactions`, { emoji });
    },
    onSuccess: () => {
      // Invalidate messages query to refresh reactions
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      // Also invalidate thread replies in case this message is in a thread
      queryClient.invalidateQueries({ queryKey: ['message-replies'] });
      setShowEmojiPicker(false);
    },
    onError: (error: any) => {
      console.error('Failed to add reaction:', error);
      // If user already reacted, try to remove instead
      if (error.response?.status === 400) {
        console.log('User may have already reacted with this emoji');
      }
    },
  });

  const removeReactionMutation = useMutation({
    mutationFn: async (emoji: string) => {
      return await messageApi.delete(`/messages/${message.id}/reactions/${encodeURIComponent(emoji)}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      // Also invalidate thread replies in case this message is in a thread
      queryClient.invalidateQueries({ queryKey: ['message-replies'] });
    },
    onError: (error) => {
      console.error('Failed to remove reaction:', error);
    },
  });

  const deleteMessageMutation = useMutation({
    mutationFn: async () => {
      return await messageApi.delete(`/messages/${message.id}`);
    },
    onSuccess: () => {
      // Invalidate messages query to refresh the list
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      // Also invalidate thread replies in case this message is in a thread
      queryClient.invalidateQueries({ queryKey: ['message-replies'] });
    },
    onError: (error) => {
      console.error('Failed to delete message:', error);
      alert('Failed to delete message. Please try again.');
    },
  });

  const handleReactionClick = (emoji: string) => {
    addReactionMutation.mutate(emoji);
  };

  const handleEmojiClick = (emoji: string, userReacted: boolean) => {
    if (userReacted) {
      removeReactionMutation.mutate(emoji);
    } else {
      addReactionMutation.mutate(emoji);
    }
  };

  const handleDeleteMessage = () => {
    if (confirm('Are you sure you want to delete this message?')) {
      deleteMessageMutation.mutate();
    }
  };

  const handleNameClick = (e: React.MouseEvent) => {
    if (nameRef.current) {
      const rect = nameRef.current.getBoundingClientRect();
      setProfilePosition({
        x: rect.left + rect.width / 2,
        y: rect.bottom,
      });
      setShowUserProfile(true);
    }
  };

  // Function to highlight matching text
  const getHighlightedText = (text: string, highlight?: string) => {
    if (!highlight || !highlight.trim()) {
      return <span>{text}</span>;
    }

    const parts = text.split(new RegExp(`(${highlight})`, 'gi'));
    return (
      <span>
        {parts.map((part, index) =>
          part.toLowerCase() === highlight.toLowerCase() ? (
            <mark key={index} className="bg-yellow-200 font-semibold">
              {part}
            </mark>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </span>
    );
  };

  const formattedTime = formatDistanceToNow(new Date(message.created_at), {
    addSuffix: true,
  });

  const displayTime = new Date(message.created_at).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  const handleDownloadFile = async (fileId: string, filename: string) => {
    try {
      // Get access token from AuthService
      const tokens = AuthService.getTokens();
      console.log('[Download] Starting download for file:', fileId, filename);
      console.log('[Download] Token available:', !!tokens?.access_token);

      if (!tokens?.access_token) {
        console.error('[Download] No access token available');
        alert('Authentication required. Please refresh the page and try again.');
        return;
      }

      // Use filesApi to get the file with authentication
      const downloadUrl = `${config.api.files}/api/v1/files/${fileId}/download`;
      console.log('[Download] Fetching from:', downloadUrl);

      const response = await fetch(downloadUrl, {
        headers: {
          'Authorization': `Bearer ${tokens.access_token}`,
        },
      });

      console.log('[Download] Response status:', response.status, response.statusText);

      if (!response.ok) {
        if (response.status === 401) {
          console.error('[Download] 401 Unauthorized - token may be expired');
          alert('Your session has expired. Please refresh the page and try again.');
        } else {
          console.error('[Download] Download failed with status:', response.status);
          alert(`Download failed: ${response.statusText}`);
        }
        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }

      // Get the blob from response
      const blob = await response.blob();
      console.log('[Download] Blob received, size:', blob.size);

      // Create a temporary URL for the blob
      const url = window.URL.createObjectURL(blob);

      // Create a temporary link and click it to trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();

      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      console.log('[Download] Download completed successfully');
    } catch (error) {
      console.error('[Download] Error downloading file:', error);
    }
  };

  return (
    <div
      className="group hover:bg-gray-100 px-4 py-1 rounded"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex space-x-3">
        {showAvatar ? (
          <div className="w-10 h-10 rounded bg-blue-500 flex items-center justify-center flex-shrink-0 overflow-hidden">
            {(message.author?.avatar_url || message.author_avatar_url) ? (
              <img
                src={message.author?.avatar_url || message.author_avatar_url}
                alt={message.author?.display_name || message.author?.username || 'User'}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-white font-medium">
                {message.author?.display_name?.[0]?.toUpperCase() ||
                  message.author?.username?.[0]?.toUpperCase() ||
                  message.author_display_name?.[0]?.toUpperCase() ||
                  message.author_username?.[0]?.toUpperCase() ||
                  'U'}
              </span>
            )}
          </div>
        ) : (
          <div className="w-10 flex-shrink-0 flex items-center justify-center">
            <span className="text-xs text-gray-500 opacity-0 group-hover:opacity-100">
              {displayTime}
            </span>
          </div>
        )}

        <div className="flex-1 min-w-0">
          {showAvatar && (
            <div className="flex items-baseline space-x-2 mb-1">
              <span
                ref={nameRef}
                onClick={handleNameClick}
                className="font-semibold text-gray-900 hover:underline cursor-pointer"
              >
                {message.author?.display_name ||
                 message.author?.username ||
                 message.author_display_name ||
                 message.author_username ||
                 'Unknown User'}
              </span>
              <span className="text-xs text-gray-500">{formattedTime}</span>
              {message.is_edited && (
                <span className="text-xs text-gray-500">(edited)</span>
              )}
            </div>
          )}

          <div className="text-gray-900 break-words">{getHighlightedText(message.content, highlightText)}</div>

          {/* Attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 space-y-2">
              {message.attachments.map((file) => {
                const isImage = file.mime_type?.startsWith('image/');
                const isVideo = file.mime_type?.startsWith('video/');
                const FileIcon = isImage ? FileImage : isVideo ? FileVideo : FileText;

                return (
                  <div
                    key={file.id}
                    className="border border-gray-300 rounded-lg p-3 bg-white hover:bg-gray-50 transition-colors max-w-md"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                        <FileIcon className="h-8 w-8 text-gray-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {file.original_filename}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(file.size_bytes / 1024).toFixed(2)} KB
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDownloadFile(file.id, file.original_filename)}
                        className="ml-3 p-2 hover:bg-gray-200 rounded transition-colors"
                        title="Download"
                      >
                        <Download className="h-5 w-5 text-gray-600" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Reactions */}
          {(message.reactions && message.reactions.length > 0) || showEmojiPicker ? (
            <div className="flex flex-wrap gap-1 mt-2">
              {message.reactions && message.reactions.map((reaction) => (
                <button
                  key={reaction.emoji}
                  onClick={() => handleEmojiClick(reaction.emoji, reaction.user_reacted)}
                  className={`flex items-center space-x-1 px-2 py-1 border rounded-full text-sm transition-colors ${
                    reaction.user_reacted
                      ? 'bg-blue-100 border-blue-500 text-blue-700'
                      : 'bg-white border-gray-300 hover:border-blue-500'
                  }`}
                  title={reaction.users?.map(u => u.username).join(', ')}
                >
                  <span>{reaction.emoji}</span>
                  <span className={reaction.user_reacted ? 'text-blue-700' : 'text-gray-600'}>
                    {reaction.count}
                  </span>
                </button>
              ))}
              {!showEmojiPicker && (
                <button
                  onClick={() => setShowEmojiPicker(true)}
                  className="flex items-center px-2 py-1 bg-white border border-gray-300 rounded-full hover:border-blue-500"
                >
                  <Smile className="h-4 w-4 text-gray-500" />
                </button>
              )}
              {/* Quick emoji picker */}
              {showEmojiPicker && (
                <div className="flex items-center gap-1 p-2 bg-white border border-gray-300 rounded-lg shadow-lg">
                  {quickEmojis.map((emoji) => (
                    <button
                      key={emoji}
                      onClick={() => handleReactionClick(emoji)}
                      className="text-2xl hover:bg-gray-100 p-1 rounded transition-colors"
                    >
                      {emoji}
                    </button>
                  ))}
                  <button
                    onClick={() => setShowEmojiPicker(false)}
                    className="ml-2 text-gray-400 hover:text-gray-600 text-sm px-2"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>
          ) : null}

          {/* Thread indicator */}
          {message.reply_count && message.reply_count > 0 && (
            <button
              onClick={() => onReplyClick?.(message)}
              className="flex items-center space-x-2 mt-2 text-blue-600 hover:bg-blue-50 px-3 py-1 rounded transition-colors"
            >
              <MessageSquare className="h-4 w-4" />
              <span className="text-sm font-medium">
                {message.reply_count} {message.reply_count === 1 ? 'reply' : 'replies'}
              </span>
            </button>
          )}
        </div>

        {/* Hover actions */}
        {showActions && (
          <div className="flex items-center space-x-1 bg-white border border-gray-300 rounded shadow-sm px-2">
            <button
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              className="p-1 hover:bg-gray-100 rounded"
              title="Add reaction"
            >
              <Smile className="h-4 w-4 text-gray-600" />
            </button>
            <button
              onClick={() => onReplyClick?.(message)}
              className="p-1 hover:bg-gray-100 rounded"
              title="Reply in thread"
            >
              <MessageSquare className="h-4 w-4 text-gray-600" />
            </button>
            {canDelete && (
              <button
                onClick={handleDeleteMessage}
                className="p-1 hover:bg-red-100 rounded"
                title="Delete message"
                disabled={deleteMessageMutation.isPending}
              >
                <Trash2 className="h-4 w-4 text-red-600" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* User Profile Popup */}
      {message.author && (
        <UserProfilePopup
          user={message.author}
          isOpen={showUserProfile}
          onClose={() => setShowUserProfile(false)}
          position={profilePosition}
        />
      )}
    </div>
  );
}
