'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Message } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import { Smile, MessageSquare, MoreVertical } from 'lucide-react';
import { messageApi } from '@/lib/api';

interface MessageItemProps {
  message: Message;
  showAvatar: boolean;
  onReplyClick?: (message: Message) => void;
}

export function MessageItem({ message, showAvatar, onReplyClick }: MessageItemProps) {
  const [showActions, setShowActions] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const queryClient = useQueryClient();

  // Common emojis for quick reactions
  const quickEmojis = ['👍', '❤️', '😂', '🎉', '👀', '🔥'];

  const addReactionMutation = useMutation({
    mutationFn: async (emoji: string) => {
      return await messageApi.post(`/messages/${message.id}/reactions`, { emoji });
    },
    onSuccess: () => {
      // Invalidate messages query to refresh reactions
      queryClient.invalidateQueries({ queryKey: ['messages'] });
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
    },
    onError: (error) => {
      console.error('Failed to remove reaction:', error);
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

  const formattedTime = formatDistanceToNow(new Date(message.created_at), {
    addSuffix: true,
  });

  const displayTime = new Date(message.created_at).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  return (
    <div
      className="group hover:bg-gray-100 px-4 py-1 rounded"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex space-x-3">
        {showAvatar ? (
          <div className="w-10 h-10 rounded bg-blue-500 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-medium">
              {message.author?.display_name?.[0]?.toUpperCase() ||
                message.author?.username?.[0]?.toUpperCase() ||
                message.author_display_name?.[0]?.toUpperCase() ||
                message.author_username?.[0]?.toUpperCase() ||
                'U'}
            </span>
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
              <span className="font-semibold text-gray-900">
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

          <div className="text-gray-900 break-words">{message.content}</div>

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
            <button className="p-1 hover:bg-gray-100 rounded" title="More actions">
              <MoreVertical className="h-4 w-4 text-gray-600" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
