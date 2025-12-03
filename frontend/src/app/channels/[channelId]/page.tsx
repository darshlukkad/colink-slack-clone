'use client';

import { use, useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { channelApi, messageApi } from '@/lib/api';
import { Channel, Message } from '@/types';
import { ChannelHeader } from '@/components/ChannelHeader';
import { MessageList } from '@/components/MessageList';
import { MessageInput } from '@/components/MessageInput';
import { TypingIndicator } from '@/components/TypingIndicator';
import { ThreadPanel } from '@/components/ThreadPanel';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { useAuthStore } from '@/store/authStore';

interface ChannelPageProps {
  params: Promise<{
    channelId: string;
  }>;
}

export default function ChannelPage({ params }: ChannelPageProps) {
  const { channelId } = use(params);
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const { joinChannel, leaveChannel, onNewMessage, onMessageUpdated, onMessageDeleted, onTyping, onReactionAdded, onReactionRemoved } = useWebSocket();
  const [typingUsers, setTypingUsers] = useState<Map<string, string>>(new Map()); // userId -> username
  const [selectedThread, setSelectedThread] = useState<Message | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const { data: channel, isLoading: channelLoading } = useQuery({
    queryKey: ['channel', channelId],
    queryFn: async () => {
      return await channelApi.get<Channel>(`/channels/${channelId}`);
    },
  });

  const [hasMore, setHasMore] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const { data: messages = [], isLoading: messagesLoading } = useQuery({
    queryKey: ['messages', channelId],
    queryFn: async () => {
      try {
        console.log(`[MESSAGES QUERY] Fetching messages for channel: ${channelId}`);
        const data = await messageApi.get<{messages: Message[], has_more: boolean, next_cursor?: string}>(`/channels/${channelId}/messages`);
        console.log(`[MESSAGES QUERY] Raw API response:`, data);
        console.log(`[MESSAGES QUERY] Number of messages:`, data.messages?.length || 0);

        // Set pagination state
        setHasMore(data.has_more || false);

        // Unwrap the messages array and map flat author fields to author object
        if (Array.isArray(data.messages)) {
          const messagesWithAuthor = data.messages.map(msg => ({
            ...msg,
            author: {
              id: msg.author_id,
              username: msg.author_username || '',
              display_name: msg.author_display_name,
              email: '',
              status: 'ACTIVE' as const,
              role: 'MEMBER' as const,
            }
          }));
          // Reverse to show oldest first (messages come from API in desc order)
          const reversed = messagesWithAuthor.reverse();
          console.log(`[MESSAGES QUERY] Returning ${reversed.length} messages (reversed):`, reversed.map(m => ({ id: m.id, content: m.content.substring(0, 20), reply_count: m.reply_count })));
          return reversed;
        }
        console.log('[MESSAGES QUERY] No messages array in response, returning empty array');
        return [];
      } catch (error) {
        console.error('[MESSAGES QUERY] Failed to fetch messages:', error);
        return [];
      }
    },
    staleTime: 0, // Always refetch on mount
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
  });

  const loadMoreMessages = async () => {
    if (!hasMore || isLoadingMore || messages.length === 0) return;

    setIsLoadingMore(true);
    try {
      // Get the oldest message ID (first in array since we reversed)
      const oldestMessageId = messages[0].id;
      console.log(`[LOAD MORE] Fetching older messages before: ${oldestMessageId}`);

      const data = await messageApi.get<{messages: Message[], has_more: boolean, next_cursor?: string}>(
        `/channels/${channelId}/messages?before=${oldestMessageId}`
      );

      console.log(`[LOAD MORE] Fetched ${data.messages?.length || 0} older messages`);

      // Update pagination state
      setHasMore(data.has_more || false);

      if (Array.isArray(data.messages) && data.messages.length > 0) {
        const messagesWithAuthor = data.messages.map(msg => ({
          ...msg,
          author: {
            id: msg.author_id,
            username: msg.author_username || '',
            display_name: msg.author_display_name,
            email: '',
            status: 'ACTIVE' as const,
            role: 'MEMBER' as const,
          }
        }));

        // Reverse and prepend to existing messages
        const reversed = messagesWithAuthor.reverse();

        queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
          return [...reversed, ...old] as Message[];
        });
      }
    } catch (error) {
      console.error('[LOAD MORE] Failed to load more messages:', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Join/leave channel on WebSocket
  useEffect(() => {
    if (channelId) {
      joinChannel(channelId);
      return () => {
        leaveChannel(channelId);
      };
    }
  }, [channelId, joinChannel, leaveChannel]);

  // Mark channel as read when messages are loaded
  useEffect(() => {
    const markAsRead = async () => {
      if (channelId && messages.length > 0 && !messagesLoading) {
        try {
          await channelApi.post(`/channels/${channelId}/read`, {});
          // Invalidate channels query to update unread counts
          queryClient.invalidateQueries({ queryKey: ['channels'] });
        } catch (error) {
          console.error('Failed to mark channel as read:', error);
        }
      }
    };

    markAsRead();
  }, [channelId, messages.length, messagesLoading, queryClient]);

  // Listen for new messages
  useEffect(() => {
    const unsubscribe = onNewMessage((newMessage) => {
      if (newMessage.channel_id === channelId) {
        // Only add top-level messages (not thread replies) to main conversation
        if (!newMessage.thread_id) {
          queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
            // Check if message already exists
            if (old.some(msg => msg.id === newMessage.id)) {
              return old;
            }
            return [...old, newMessage];
          });
        } else if (newMessage.parent_message_id) {
          // This is a thread reply - increment the reply count of the parent message
          queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
            return old.map(msg => {
              if (msg.id === newMessage.parent_message_id) {
                return {
                  ...msg,
                  reply_count: (msg.reply_count || 0) + 1,
                };
              }
              return msg;
            });
          });
        }
      }
    });

    return unsubscribe;
  }, [channelId, onNewMessage, queryClient]);

  // Listen for message updates
  useEffect(() => {
    const unsubscribe = onMessageUpdated((updatedMessage) => {
      if (updatedMessage.channel_id === channelId) {
        queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
          return old.map(msg =>
            msg.id === updatedMessage.id ? updatedMessage : msg
          );
        });
      }
    });

    return unsubscribe;
  }, [channelId, onMessageUpdated, queryClient]);

  // Listen for message deletions
  useEffect(() => {
    const unsubscribe = onMessageDeleted((messageId) => {
      queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
        return old.filter(msg => msg.id !== messageId);
      });
    });

    return unsubscribe;
  }, [channelId, onMessageDeleted, queryClient]);

  // Listen for typing indicators
  useEffect(() => {
    const currentUserId = currentUser?.id;

    const unsubscribe = onTyping((data) => {
      if (data.channelId === channelId && data.userId !== currentUserId) {
        setTypingUsers((prev) => {
          const next = new Map(prev);
          if (data.isTyping) {
            // Use display name from the event, with fallback to username or user ID
            const displayName = data.displayName || data.username || data.userId;
            next.set(data.userId, displayName);

            // Auto-remove after 3 seconds
            setTimeout(() => {
              setTypingUsers((current) => {
                const updated = new Map(current);
                updated.delete(data.userId);
                return updated;
              });
            }, 3000);
          } else {
            next.delete(data.userId);
          }
          return next;
        });
      }
    });

    return unsubscribe;
  }, [channelId, onTyping, currentUser?.id]);

  // Listen for reaction added
  useEffect(() => {
    const unsubscribe = onReactionAdded((data) => {
      if (data.channel_id === channelId) {
        // Update main messages
        queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
          return old.map(msg => {
            if (msg.id === data.message_id) {
              const reactions = msg.reactions || [];
              const existingReaction = reactions.find(r => r.emoji === data.emoji);

              if (existingReaction) {
                // Increment count and add user
                return {
                  ...msg,
                  reactions: reactions.map(r =>
                    r.emoji === data.emoji
                      ? {
                          ...r,
                          count: r.count + 1,
                          users: [...r.users, { id: data.user_id, username: data.username }],
                          user_reacted: data.user_id === currentUser?.id ? true : r.user_reacted,
                        }
                      : r
                  ),
                };
              } else {
                // Add new reaction
                return {
                  ...msg,
                  reactions: [
                    ...reactions,
                    {
                      emoji: data.emoji,
                      count: 1,
                      users: [{ id: data.user_id, username: data.username }],
                      user_reacted: data.user_id === currentUser?.id,
                    },
                  ],
                };
              }
            }
            return msg;
          });
        });

        // Also invalidate thread replies in case this message is in a thread
        queryClient.invalidateQueries({ queryKey: ['message-replies'] });
      }
    });

    return unsubscribe;
  }, [channelId, onReactionAdded, queryClient, currentUser?.id]);

  // Listen for reaction removed
  useEffect(() => {
    const unsubscribe = onReactionRemoved((data) => {
      if (data.channel_id === channelId) {
        // Update main messages
        queryClient.setQueryData<Message[]>(['messages', channelId], (old = []) => {
          return old.map(msg => {
            if (msg.id === data.message_id) {
              const reactions = msg.reactions || [];
              return {
                ...msg,
                reactions: reactions
                  .map(r => {
                    if (r.emoji === data.emoji) {
                      return {
                        ...r,
                        count: r.count - 1,
                        users: r.users.filter(u => u.id !== data.user_id),
                        user_reacted: data.user_id === currentUser?.id ? false : r.user_reacted,
                      };
                    }
                    return r;
                  })
                  .filter(r => r.count > 0), // Remove reactions with 0 count
              };
            }
            return msg;
          });
        });

        // Also invalidate thread replies in case this message is in a thread
        queryClient.invalidateQueries({ queryKey: ['message-replies'] });
      }
    });

    return unsubscribe;
  }, [channelId, onReactionRemoved, queryClient, currentUser?.id]);

  if (channelLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  if (!channel) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Channel not found</h2>
          <p className="text-gray-600">This channel may have been deleted or you don't have access</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full relative">
      <ChannelHeader channel={channel} onSearch={setSearchQuery} />
      <MessageList
        messages={messages}
        isLoading={messagesLoading}
        onReplyClick={setSelectedThread}
        hasMore={hasMore}
        isLoadingMore={isLoadingMore}
        onLoadMore={loadMoreMessages}
        searchQuery={searchQuery}
      />
      <TypingIndicator usernames={Array.from(typingUsers.values())} />
      <MessageInput channelId={channelId} />

      {/* Thread Panel */}
      {selectedThread && (
        <ThreadPanel
          message={selectedThread}
          onClose={() => setSelectedThread(null)}
        />
      )}
    </div>
  );
}
