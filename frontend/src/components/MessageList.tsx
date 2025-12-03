'use client';

import { useEffect, useRef } from 'react';
import { Message } from '@/types';
import { MessageItem } from './MessageItem';
import { ChevronUp } from 'lucide-react';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onReplyClick?: (message: Message) => void;
  hasMore?: boolean;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
  searchQuery?: string;
}

export function MessageList({ messages, isLoading, onReplyClick, hasMore, isLoadingMore, onLoadMore, searchQuery }: MessageListProps) {
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

  // Filter messages based on search query
  const filteredMessages = searchQuery
    ? messages.filter(msg => msg.content.toLowerCase().includes(searchQuery.toLowerCase()))
    : messages;

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

  if (searchQuery && filteredMessages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-600 text-lg">No messages found</p>
          <p className="text-gray-500 text-sm mt-2">No messages contain "{searchQuery}"</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 px-4 py-4">
      {searchQuery && (
        <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
          <p className="text-sm text-purple-800">
            Showing {filteredMessages.length} message{filteredMessages.length !== 1 ? 's' : ''} matching "{searchQuery}"
          </p>
        </div>
      )}
      <div className="space-y-4">
        {/* Load More Button - only show when not searching */}
        {!searchQuery && hasMore && (
          <div className="flex justify-center pb-4">
            <button
              onClick={onLoadMore}
              disabled={isLoadingMore}
              className="flex items-center space-x-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
            >
              {isLoadingMore ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-900"></div>
                  <span className="text-sm font-medium text-gray-700">Loading...</span>
                </>
              ) : (
                <>
                  <ChevronUp className="h-4 w-4 text-gray-600" />
                  <span className="text-sm font-medium text-gray-700">Load older messages</span>
                </>
              )}
            </button>
          </div>
        )}

        {filteredMessages.map((message, index) => {
          const previousMessage = index > 0 ? filteredMessages[index - 1] : null;
          const showAvatar = !previousMessage || previousMessage.author_id !== message.author_id;

          return (
            <MessageItem
              key={message.id}
              message={message}
              showAvatar={showAvatar}
              onReplyClick={onReplyClick}
              highlightText={searchQuery}
            />
          );
        })}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
