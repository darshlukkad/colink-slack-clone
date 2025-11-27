'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Send } from 'lucide-react';
import { messageApi, threadsApi } from '@/lib/api';
import { Message } from '@/types';
import { MessageItem } from './MessageItem';
import { useWebSocket } from '@/contexts/WebSocketContext';

interface ThreadPanelProps {
  message: Message;
  onClose: () => void;
}

interface ThreadReply {
  id: string;
  content: string;
  author_id: string;
  author_username: string;
  author_display_name?: string;
  thread_id: string | null;
  message_type: string;
  is_edited: boolean;
  created_at: string;
  updated_at: string;
}

export function ThreadPanel({ message, onClose }: ThreadPanelProps) {
  const [replyContent, setReplyContent] = useState('');
  const [isSending, setIsSending] = useState(false);
  const { onNewMessage } = useWebSocket();

  // Fetch thread replies using parent message ID
  const { data: threadData, isLoading, refetch } = useQuery({
    queryKey: ['message-replies', message.id],
    queryFn: async () => {
      console.log('[ThreadPanel] Fetching replies for message:', message.id);
      const data = await threadsApi.get<{ replies: ThreadReply[]; total_count: number; has_more: boolean }>(
        `/messages/${message.id}/replies`
      );
      console.log('[ThreadPanel] Received replies:', data);
      return data;
    },
  });

  // Listen for new messages in this thread
  useEffect(() => {
    const messageId = message.id;
    const threadId = message.thread_id;

    const unsubscribe = onNewMessage((newMessage) => {
      // Refetch if new message is a reply to this message
      // Check parent_message_id from the response or if thread_id matches
      if (newMessage.parent_message_id === messageId ||
          (newMessage.thread_id && threadId && newMessage.thread_id === threadId)) {
        refetch();
      }
    });

    return unsubscribe;
  }, [message.id, message.thread_id, onNewMessage, refetch]);

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyContent.trim() || isSending) return;

    setIsSending(true);
    try {
      await messageApi.post('/messages', {
        channel_id: message.channel_id,
        content: replyContent.trim(),
        parent_id: message.id, // This creates/adds to thread
        message_type: 'text',
      });

      setReplyContent('');
      // Refetch replies to show the new one
      setTimeout(() => refetch(), 500);
    } catch (error) {
      console.error('Failed to send reply:', error);
    } finally {
      setIsSending(false);
    }
  };

  const replies = threadData?.replies || [];

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white border-l border-gray-200 shadow-lg flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h2 className="text-lg font-semibold">Thread</h2>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Original Message */}
      <div className="border-b border-gray-200 p-4 bg-gray-50">
        <MessageItem message={message} showAvatar={true} />
      </div>

      {/* Thread Replies */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {isLoading ? (
          <div className="text-center text-gray-500 py-4">Loading replies...</div>
        ) : replies.length === 0 ? (
          <div className="text-center text-gray-500 py-4">
            No replies yet. Start the conversation!
          </div>
        ) : (
          replies.map((reply) => {
            // Convert ThreadReply to Message format
            const replyMessage: Message = {
              id: reply.id,
              channel_id: message.channel_id,
              author_id: reply.author_id,
              author_username: reply.author_username,
              author_display_name: reply.author_display_name,
              content: reply.content,
              thread_id: reply.thread_id || undefined,
              message_type: reply.message_type as 'text' | 'file' | 'system',
              is_edited: reply.is_edited,
              created_at: reply.created_at,
              updated_at: reply.updated_at,
            };

            return (
              <MessageItem
                key={reply.id}
                message={replyMessage}
                showAvatar={true}
              />
            );
          })
        )}
      </div>

      {/* Reply Input */}
      <div className="border-t border-gray-200 p-4">
        <form onSubmit={handleSendReply} className="flex flex-col space-y-2">
          <textarea
            value={replyContent}
            onChange={(e) => setReplyContent(e.target.value)}
            placeholder="Reply to thread..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
            rows={3}
            disabled={isSending}
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!replyContent.trim() || isSending}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="h-4 w-4" />
              <span>{isSending ? 'Sending...' : 'Send'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
