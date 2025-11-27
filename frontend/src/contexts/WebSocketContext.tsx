'use client';

import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/authStore';
import { config } from '@/lib/config';
import type { Message } from '@/types';

interface ReactionData {
  message_id: string;
  channel_id: string;
  user_id: string;
  username: string;
  emoji: string;
}

interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  joinChannel: (channelId: string) => void;
  leaveChannel: (channelId: string) => void;
  sendMessage: (channelId: string, content: string) => void;
  sendTyping: (channelId: string, isTyping: boolean) => void;
  onNewMessage: (callback: (message: Message) => void) => () => void;
  onMessageUpdated: (callback: (message: Message) => void) => () => void;
  onMessageDeleted: (callback: (messageId: string) => void) => () => void;
  onTyping: (callback: (data: { userId: string; channelId: string; isTyping: boolean; username?: string; displayName?: string }) => void) => () => void;
  onUserStatusChange: (callback: (data: { userId: string; status: string }) => void) => () => void;
  onReactionAdded: (callback: (data: ReactionData) => void) => () => void;
  onReactionRemoved: (callback: (data: ReactionData) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
}

interface WebSocketProviderProps {
  children: React.ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const { tokens, isAuthenticated } = useAuthStore();
  const socketRef = useRef<Socket | null>(null);

  // Initialize WebSocket connection
  useEffect(() => {
    if (!isAuthenticated || !tokens?.access_token) {
      // Disconnect if not authenticated
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
        setSocket(null);
        setIsConnected(false);
      }
      return;
    }

    // Create socket connection
    const newSocket = io(config.websocket.url, {
      auth: {
        token: tokens.access_token,
      },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
      timeout: 10000,
    });

    // Connection event handlers
    newSocket.on('connect', () => {
      console.log('✅ WebSocket connected:', newSocket.id);
      setIsConnected(true);
    });

    newSocket.on('disconnect', (reason) => {
      console.log('📡 WebSocket disconnected:', reason);
      setIsConnected(false);
    });

    newSocket.on('connect_error', (error) => {
      console.warn('⚠️  WebSocket connection error (WebSocket server may not be available):', error.message);
      setIsConnected(false);
      // Don't throw error, just log it - app will work without WebSocket
    });

    newSocket.on('error', (error) => {
      console.warn('⚠️  WebSocket error:', error);
      // Don't throw error, just log it
    });

    socketRef.current = newSocket;
    setSocket(newSocket);

    // Cleanup on unmount
    return () => {
      if (newSocket) {
        newSocket.disconnect();
      }
    };
  }, [isAuthenticated, tokens?.access_token]);

  // Join a channel
  const joinChannel = useCallback((channelId: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('join_channel', { channel_id: channelId });
      console.log('Joined channel:', channelId);
    }
  }, []);

  // Leave a channel
  const leaveChannel = useCallback((channelId: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('leave_channel', { channel_id: channelId });
      console.log('Left channel:', channelId);
    }
  }, []);

  // Send a message
  const sendMessage = useCallback((channelId: string, content: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('send_message', {
        channel_id: channelId,
        content,
        message_type: 'text',
      });
    }
  }, []);

  // Send typing indicator
  const sendTyping = useCallback((channelId: string, isTyping: boolean) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('typing', {
        channel_id: channelId,
        is_typing: isTyping,
      });
    }
  }, []);

  // Listen for new messages
  const onNewMessage = useCallback((callback: (message: Message) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (message: Message) => {
      callback(message);
    };

    socketRef.current.on('new_message', handler);

    return () => {
      socketRef.current?.off('new_message', handler);
    };
  }, []);

  // Listen for message updates
  const onMessageUpdated = useCallback((callback: (message: Message) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (message: Message) => {
      callback(message);
    };

    socketRef.current.on('message_updated', handler);

    return () => {
      socketRef.current?.off('message_updated', handler);
    };
  }, []);

  // Listen for message deletions
  const onMessageDeleted = useCallback((callback: (messageId: string) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (data: { message_id: string }) => {
      callback(data.message_id);
    };

    socketRef.current.on('message_deleted', handler);

    return () => {
      socketRef.current?.off('message_deleted', handler);
    };
  }, []);

  // Listen for typing indicators
  const onTyping = useCallback((callback: (data: { userId: string; channelId: string; isTyping: boolean; username?: string; displayName?: string }) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (data: { user_id: string; channel_id: string; is_typing: boolean; username?: string; display_name?: string }) => {
      callback({
        userId: data.user_id,
        channelId: data.channel_id,
        isTyping: data.is_typing,
        username: data.username,
        displayName: data.display_name,
      });
    };

    socketRef.current.on('user_typing', handler);

    return () => {
      socketRef.current?.off('user_typing', handler);
    };
  }, []);

  // Listen for user status changes
  const onUserStatusChange = useCallback((callback: (data: { userId: string; status: string }) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (data: { user_id: string; status: string }) => {
      callback({
        userId: data.user_id,
        status: data.status,
      });
    };

    socketRef.current.on('user_status_change', handler);

    return () => {
      socketRef.current?.off('user_status_change', handler);
    };
  }, []);

  // Listen for reaction added
  const onReactionAdded = useCallback((callback: (data: ReactionData) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (data: ReactionData) => {
      callback(data);
    };

    socketRef.current.on('reaction_added', handler);

    return () => {
      socketRef.current?.off('reaction_added', handler);
    };
  }, []);

  // Listen for reaction removed
  const onReactionRemoved = useCallback((callback: (data: ReactionData) => void) => {
    if (!socketRef.current) return () => {};

    const handler = (data: ReactionData) => {
      callback(data);
    };

    socketRef.current.on('reaction_removed', handler);

    return () => {
      socketRef.current?.off('reaction_removed', handler);
    };
  }, []);

  const value: WebSocketContextType = {
    socket,
    isConnected,
    joinChannel,
    leaveChannel,
    sendMessage,
    sendTyping,
    onNewMessage,
    onMessageUpdated,
    onMessageDeleted,
    onTyping,
    onUserStatusChange,
    onReactionAdded,
    onReactionRemoved,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}
