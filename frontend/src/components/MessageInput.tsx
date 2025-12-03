'use client';

import { useState, useRef, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { messageApi, filesApi } from '@/lib/api';
import { Send, Paperclip, Smile, X } from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';

interface MessageInputProps {
  channelId: string;
}

interface UploadedFile {
  id: string;
  filename: string;
  url: string;
  content_type: string;
  size: number;
}

export function MessageInput({ channelId }: MessageInputProps) {
  const [content, setContent] = useState('');
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { sendTyping } = useWebSocket();
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Common emojis for quick access
  const quickEmojis = ['😊', '👍', '❤️', '😂', '🎉', '👀', '🔥', '✅', '🚀', '💯'];

  const sendMessageMutation = useMutation({
    mutationFn: async (messageContent: string) => {
      const payload: any = {
        content: messageContent,
        channel_id: channelId,
        message_type: 'text',
      };

      // Include file IDs if there are attachments
      if (attachedFiles.length > 0) {
        payload.attachment_ids = attachedFiles.map(f => f.id);
      }

      const response = await messageApi.post<any>(`/messages`, payload);
      console.log('Message sent:', response);
      return response;
    },
    onSuccess: async (newMessage) => {
      setContent('');
      setAttachedFiles([]); // Clear attached files
      sendTyping(channelId, false); // Stop typing indicator
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = null;
      }

      // Refetch messages immediately
      await queryClient.refetchQueries({ queryKey: ['messages', channelId] });
    },
    onError: (error) => {
      console.error('Failed to send message:', error);
    },
  });

  const handleTyping = useCallback(() => {
    // Send typing indicator
    sendTyping(channelId, true);

    // Clear existing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Stop typing after 2 seconds of inactivity
    typingTimeoutRef.current = setTimeout(() => {
      sendTyping(channelId, false);
      typingTimeoutRef.current = null;
    }, 2000);
  }, [channelId, sendTyping]);

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    if (e.target.value.trim()) {
      handleTyping();
    } else {
      // Stop typing if content is empty
      sendTyping(channelId, false);
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = null;
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Allow sending if there's content OR attachments
    if (content.trim() || attachedFiles.length > 0) {
      sendMessageMutation.mutate(content.trim() || '📎'); // Use paperclip emoji if no text
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleEmojiClick = (emoji: string) => {
    setContent(prev => prev + emoji);
    setShowEmojiPicker(false);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      const uploadPromises = Array.from(files).map(async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('channel_id', channelId);

        // Content-Type will be automatically set by browser for FormData
        const response = await filesApi.post<UploadedFile>('/api/v1/files/upload', formData);

        return response;
      });

      const uploadedFiles = await Promise.all(uploadPromises);
      setAttachedFiles(prev => [...prev, ...uploadedFiles]);
    } catch (error) {
      console.error('Failed to upload files:', error);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveFile = (fileId: string) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="border-t border-gray-200 bg-white px-4 py-4">
      <form onSubmit={handleSubmit}>
        <div className="flex items-end space-x-2">
          <div className="flex-1 border border-gray-300 rounded-lg overflow-hidden focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500">
            {/* Attached files preview */}
            {attachedFiles.length > 0 && (
              <div className="px-4 pt-3 pb-2 border-b border-gray-200">
                <div className="flex flex-wrap gap-2">
                  {attachedFiles.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center space-x-2 bg-gray-100 px-3 py-2 rounded-lg"
                    >
                      <Paperclip className="h-4 w-4 text-gray-600" />
                      <span className="text-sm text-gray-700 max-w-[200px] truncate">
                        {file.filename}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleRemoveFile(file.id)}
                        className="text-gray-500 hover:text-gray-700"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <textarea
              value={content}
              onChange={handleContentChange}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              className="w-full px-4 py-3 resize-none outline-none max-h-32 text-gray-900"
              rows={1}
              disabled={sendMessageMutation.isPending || isUploading}
            />
            <div className="flex items-center justify-between px-4 pb-3 pt-1">
              <div className="flex items-center space-x-2 relative">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  onChange={handleFileSelect}
                  className="hidden"
                  accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt"
                />
                <button
                  type="button"
                  onClick={handleAttachClick}
                  disabled={isUploading}
                  className="p-1 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Attach file"
                >
                  {isUploading ? (
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-600"></div>
                  ) : (
                    <Paperclip className="h-5 w-5 text-gray-600" />
                  )}
                </button>
                <button
                  type="button"
                  className="p-1 hover:bg-gray-100 rounded"
                  title="Add emoji"
                  onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                >
                  <Smile className="h-5 w-5 text-gray-600" />
                </button>

                {/* Emoji Picker */}
                {showEmojiPicker && (
                  <div className="absolute bottom-full left-0 mb-2 p-2 bg-white border border-gray-300 rounded-lg shadow-lg z-10">
                    <div className="flex items-center gap-1">
                      {quickEmojis.map((emoji) => (
                        <button
                          key={emoji}
                          type="button"
                          onClick={() => handleEmojiClick(emoji)}
                          className="text-2xl hover:bg-gray-100 p-1 rounded transition-colors"
                        >
                          {emoji}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => setShowEmojiPicker(false)}
                        className="ml-2 text-gray-400 hover:text-gray-600 text-sm px-2"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <button
                type="submit"
                disabled={(!content.trim() && attachedFiles.length === 0) || sendMessageMutation.isPending || isUploading}
                className="flex items-center space-x-1 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                <Send className="h-4 w-4" />
                <span className="text-sm font-medium">Send</span>
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
