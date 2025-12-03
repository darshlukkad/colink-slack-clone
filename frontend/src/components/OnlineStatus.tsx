'use client';

import { useWebSocket } from '@/contexts/WebSocketContext';

interface OnlineStatusProps {
  userId: string;
  className?: string;
}

export function OnlineStatus({ userId, className = '' }: OnlineStatusProps) {
  const { onlineUsers } = useWebSocket();
  const isOnline = onlineUsers.has(userId);

  return (
    <div
      className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
        isOnline ? 'bg-green-500' : 'bg-gray-400'
      } ${className}`}
      title={isOnline ? 'Online' : 'Offline'}
      aria-label={isOnline ? 'User is online' : 'User is offline'}
    />
  );
}
