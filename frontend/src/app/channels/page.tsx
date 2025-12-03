'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { channelApi } from '@/lib/api';
import { Channel } from '@/types';
import { MessageSquare } from 'lucide-react';

export default function ChannelsPage() {
  const router = useRouter();

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: async () => {
      return await channelApi.get<Channel[]>('/channels');
    },
  });

  useEffect(() => {
    if (!isLoading && channels.length > 0) {
      // Redirect to first available channel
      router.push(`/channels/${channels[0].id}`);
    }
  }, [channels, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-50">
        <div className="text-center">
          <MessageSquare className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">No channels yet</h2>
          <p className="text-gray-600">Create or join a channel to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
    </div>
  );
}
