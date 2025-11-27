'use client';

import { useEffect, useRef } from 'react';
import { Message } from '@/types';
import { MessageItem } from './MessageItem';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onReplyClick?: (message: Message) => void;
}

export function MessageList({ messages, isLoading, onReplyClick }: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-600 text-lg">No messages yet</p>
          <p className="text-gray-500 text-sm mt-2">Be the first to send a message!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 px-4 py-4">
      <div className="space-y-4">
        {messages.map((message, index) => {
          const previousMessage = index > 0 ? messages[index - 1] : null;
          const showAvatar = !previousMessage || previousMessage.author_id !== message.author_id;

          return (
            <MessageItem
              key={message.id}
              message={message}
              showAvatar={showAvatar}
              onReplyClick={onReplyClick}
            />
          );
        })}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
