'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { channelApi, authApi } from '@/lib/api';
import { Channel, User } from '@/types';
import { Hash, Lock, ChevronDown, Plus, MessageSquare, Settings, LogOut } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, logout } = useAuthStore();
  const [channelsExpanded, setChannelsExpanded] = useState(true);
  const [directMessagesExpanded, setDirectMessagesExpanded] = useState(true);

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: async () => {
      try {
        const response = await channelApi.get<{ channels: Channel[] }>('/channels');
        console.log('Channels response:', response);
        // Extract channels array from response object
        const channelsData = response?.channels || [];
        return Array.isArray(channelsData) ? channelsData : [];
      } catch (error) {
        console.error('Failed to fetch channels:', error);
        return [];
      }
    },
  });

  // Fetch all users for Direct Messages list
  const { data: allUsers = [] } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      try {
        const data = await authApi.get<User[]>('/auth/users');
        console.log('Users data:', data);
        // Ensure we always return an array
        return Array.isArray(data) ? data : [];
      } catch (error) {
        console.error('Failed to fetch users:', error);
        return [];
      }
    },
  });

  const publicChannels = channels.filter(c => c.channel_type === 'PUBLIC');
  const privateChannels = channels.filter(c => c.channel_type === 'PRIVATE');
  const directMessages = channels.filter(c => c.channel_type === 'DIRECT');

  // Get users excluding current user, limit to 12
  const dmUsers = allUsers
    .filter(u => u.id !== user?.id)
    .slice(0, 12);

  const createDMMutation = useMutation({
    mutationFn: async (selectedUser: User) => {
      // Use the dedicated DM endpoint which handles finding/creating DM channels
      console.log('Creating/finding DM channel with user:', selectedUser.id);
      const channel = await channelApi.post<Channel>('/channels/dm', {
        other_user_id: selectedUser.id,
      });
      console.log('DM channel returned:', channel);
      return channel;
    },
    onSuccess: (channel) => {
      console.log('DM mutation success, navigating to:', channel.id);
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      router.push(`/channels/${channel.id}`);
    },
    onError: (error) => {
      console.error('DM mutation error:', error);
    },
  });

  const handleSelectUser = (selectedUser: User) => {
    console.log('Selecting user:', selectedUser);
    console.log('Current user:', user);
    createDMMutation.mutate(selectedUser);
  };

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="w-64 bg-purple-900 text-white flex flex-col h-screen">
      {/* Workspace Header */}
      <div className="p-4 border-b border-purple-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <MessageSquare className="h-6 w-6" />
            <h1 className="text-lg font-bold">Colink</h1>
          </div>
          <ChevronDown className="h-4 w-4" />
        </div>
      </div>

      {/* User Info */}
      <div className="px-4 py-3 border-b border-purple-800">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded bg-purple-600 flex items-center justify-center">
            <span className="text-sm font-medium">
              {user?.display_name?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.display_name || user?.username}</p>
            <p className="text-xs text-purple-300 truncate">{user?.status_text || 'Active'}</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto">
        {/* Public Channels */}
        <div className="px-2 py-2">
          <div className="w-full flex items-center justify-between px-2 py-1 text-sm">
            <button
              onClick={() => setChannelsExpanded(!channelsExpanded)}
              className="flex-1 text-left font-semibold hover:opacity-80"
            >
              Channels
            </button>
            <div className="flex items-center space-x-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  // TODO: Handle create channel
                }}
                className="hover:bg-purple-700 rounded p-0.5"
              >
                <Plus className="h-4 w-4" />
              </button>
              <button
                onClick={() => setChannelsExpanded(!channelsExpanded)}
                className="hover:bg-purple-700 rounded p-0.5"
              >
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${channelsExpanded ? '' : '-rotate-90'}`}
                />
              </button>
            </div>
          </div>

          {channelsExpanded && (
            <div className="mt-1 space-y-0.5">
              {isLoading ? (
                <div className="px-2 py-1 text-sm text-purple-300">Loading...</div>
              ) : publicChannels.length === 0 ? (
                <div className="px-2 py-1 text-sm text-purple-300">No channels yet</div>
              ) : (
                publicChannels.map((channel) => (
                  <Link
                    key={channel.id}
                    href={`/channels/${channel.id}`}
                    className={`flex items-center space-x-2 px-2 py-1 rounded text-sm hover:bg-purple-800 ${
                      pathname === `/channels/${channel.id}` ? 'bg-purple-700' : ''
                    }`}
                  >
                    <Hash className="h-4 w-4" />
                    <span className="flex-1 truncate">{channel.name}</span>
                    {channel.unread_count && channel.unread_count > 0 ? (
                      <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                        {channel.unread_count}
                      </span>
                    ) : null}
                  </Link>
                ))
              )}
            </div>
          )}
        </div>

        {/* Private Channels */}
        {privateChannels.length > 0 && (
          <div className="px-2 py-2">
            <div className="text-xs font-semibold text-purple-300 px-2 py-1">PRIVATE CHANNELS</div>
            <div className="mt-1 space-y-0.5">
              {privateChannels.map((channel) => (
                <Link
                  key={channel.id}
                  href={`/channels/${channel.id}`}
                  className={`flex items-center space-x-2 px-2 py-1 rounded text-sm hover:bg-purple-800 ${
                    pathname === `/channels/${channel.id}` ? 'bg-purple-700' : ''
                  }`}
                >
                  <Lock className="h-4 w-4" />
                  <span className="flex-1 truncate">{channel.name}</span>
                  {channel.unread_count && channel.unread_count > 0 ? (
                    <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                      {channel.unread_count}
                    </span>
                  ) : null}
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Direct Messages */}
        <div className="px-2 py-2">
          <div className="w-full flex items-center justify-between px-2 py-1 text-sm">
            <button
              onClick={() => setDirectMessagesExpanded(!directMessagesExpanded)}
              className="flex-1 text-left font-semibold hover:opacity-80"
            >
              Direct Messages
            </button>
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setDirectMessagesExpanded(!directMessagesExpanded)}
                className="hover:bg-purple-700 rounded p-0.5"
              >
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${directMessagesExpanded ? '' : '-rotate-90'}`}
                />
              </button>
            </div>
          </div>

          {directMessagesExpanded && (
            <div className="mt-1 space-y-0.5">
              {dmUsers.length === 0 ? (
                <div className="px-2 py-1 text-sm text-purple-300">No users available</div>
              ) : (
                dmUsers.map((dmUser) => {
                  // Check if we have an existing DM with this user
                  const existingDM = directMessages.find((dm) =>
                    dm.name.includes(dmUser.username)
                  );
                  const isActive = existingDM && pathname === `/channels/${existingDM.id}`;

                  return (
                    <button
                      key={dmUser.id}
                      onClick={() => handleSelectUser(dmUser)}
                      className={`w-full flex items-center space-x-2 px-2 py-1 rounded text-sm hover:bg-purple-800 ${
                        isActive ? 'bg-purple-700' : ''
                      }`}
                    >
                      <div
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          dmUser.status === 'ACTIVE'
                            ? 'bg-green-500'
                            : dmUser.status === 'INACTIVE'
                            ? 'bg-gray-400'
                            : 'bg-red-500'
                        }`}
                      ></div>
                      <span className="flex-1 truncate text-left">
                        {dmUser.display_name || dmUser.username}
                      </span>
                      {existingDM?.unread_count && existingDM.unread_count > 0 ? (
                        <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                          {existingDM.unread_count}
                        </span>
                      ) : null}
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="border-t border-purple-800 p-2">
        <button
          onClick={handleLogout}
          className="w-full flex items-center space-x-2 px-2 py-2 hover:bg-purple-800 rounded text-sm"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign out</span>
        </button>
      </div>
    </div>
  );
}
