'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { channelApi, authApi } from '@/lib/api';
import { Channel, User } from '@/types';
import { Hash, Lock, ChevronDown, Plus, MessageSquare, LogOut, BarChart3 } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { CreateChannelModal } from './CreateChannelModal';
import { OnlineStatus } from './OnlineStatus';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { ProfileModal } from './ProfileModal';

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, logout } = useAuthStore();
  const { onlineUsers } = useWebSocket();
  const [channelsExpanded, setChannelsExpanded] = useState(true);
  const [directMessagesExpanded, setDirectMessagesExpanded] = useState(true);
  const [showCreateChannelModal, setShowCreateChannelModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: async () => {
      try {
        const response = await channelApi.get<{ channels: Channel[] }>('/channels');
        console.log('📋 Channels response:', response);
        console.log('📋 DM channels:', response?.channels?.filter((c: any) => c.channel_type === 'DIRECT').map((c: any) => ({
          name: c.name,
          unread: c.unread_count
        })));
        // Extract channels array from response object
        const channelsData = response?.channels || [];
        return Array.isArray(channelsData) ? channelsData : [];
      } catch (error) {
        console.error('Failed to fetch channels:', error);
        return [];
      }
    },
    // Poll for updates every 3 seconds to keep unread counts fresh
    refetchInterval: 3000,
    refetchIntervalInBackground: true, // Continue polling even when tab is not focused
  });

  // Fetch all users for Direct Messages list
  const { data: allUsers = [] } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      try {
        const data = await authApi.get<User[]>('/auth/users');
        console.log('📋 Users data from API:', data.length, 'users');
        console.log('📋 User roles:', data.map(u => ({ username: u.username, role: u.role, roleLower: u.role?.toLowerCase() })));
        // Ensure we always return an array
        return Array.isArray(data) ? data : [];
      } catch (error) {
        console.error('Failed to fetch users:', error);
        return [];
      }
    },
  });

  // Refresh channels list when user updates to ensure DM avatars are fresh
  // This is triggered when the profile modal updates the user query cache
  useEffect(() => {
    if (user) {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    }
  }, [user?.avatar_url, user?.display_name, queryClient]);

  // Note: Real-time notifications are disabled for now
  // Using polling (refetchInterval: 3000) to refresh unread counts instead

  const publicChannels = channels.filter(c => c.channel_type === 'PUBLIC');
  const privateChannels = channels.filter(c => c.channel_type === 'PRIVATE');
  const directMessages = channels.filter(c => c.channel_type === 'DIRECT');

  // Get users excluding current user and admin users, prioritize online users, limit to 12
  const dmUsers = allUsers
    .filter(u => {
      const isCurrentUser = u.id === user?.id;
      const isAdmin = u.role?.toLowerCase() === 'admin';
      console.log(`🔍 Filtering user ${u.username}: currentUser=${isCurrentUser}, isAdmin=${isAdmin}, role=${u.role}`);
      return !isCurrentUser && !isAdmin;
    })
    .sort((a, b) => {
      const aOnline = onlineUsers.has(a.keycloak_id);
      const bOnline = onlineUsers.has(b.keycloak_id);
      if (aOnline && !bOnline) return -1;
      if (!aOnline && bOnline) return 1;
      return 0;
    })
    .slice(0, 12);

  // Debug: Log online users state
  console.log('🔍 Sidebar - Online users:', {
    count: onlineUsers.size,
    users: Array.from(onlineUsers),
    dmUsersCount: dmUsers.length,
    dmUsers: dmUsers.map(u => ({ id: u.id, keycloak_id: u.keycloak_id, name: u.display_name || u.username, online: onlineUsers.has(u.keycloak_id) }))
  });

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
      <button
        onClick={() => setShowProfileModal(true)}
        className="w-full px-4 py-3 border-b border-purple-800 hover:bg-purple-800 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded bg-purple-600 flex items-center justify-center overflow-hidden">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="Profile" className="w-full h-full object-cover" />
            ) : (
              <span className="text-sm font-medium">
                {user?.display_name?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            )}
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className="text-sm font-medium truncate">{user?.display_name || user?.username}</p>
            <p className="text-xs text-purple-300 truncate">{user?.status_text || 'Active'}</p>
          </div>
        </div>
      </button>

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
                  setShowCreateChannelModal(true);
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
                <>
                  {console.log('🎯 DM Users being rendered:', dmUsers.map(u => ({ username: u.username, role: u.role })))}
                  {dmUsers.map((dmUser) => {
                  // Check if we have an existing DM with this user
                  // DM channel names are in format: dm_<user1_id>_<user2_id>
                  const existingDM = directMessages.find((dm) =>
                    dm.name.includes(dmUser.id)
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
                      {/* Avatar with online status indicator */}
                      <div className="relative flex-shrink-0">
                        <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center overflow-hidden">
                          {dmUser.avatar_url ? (
                            <img
                              src={dmUser.avatar_url}
                              alt={dmUser.display_name || dmUser.username}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <span className="text-white text-xs font-medium">
                              {dmUser.display_name?.[0]?.toUpperCase() ||
                                dmUser.username?.[0]?.toUpperCase() ||
                                'U'}
                            </span>
                          )}
                        </div>
                        {/* Online status dot positioned at bottom-right of avatar */}
                        <div className="absolute -bottom-0.5 -right-0.5">
                          <OnlineStatus userId={dmUser.keycloak_id} className="w-3 h-3 border-2 border-purple-900" />
                        </div>
                      </div>
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
                })}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="border-t border-purple-800 p-2">
        {/* BI Analytics Dashboard Link - Only visible to admins */}
        {user?.role?.toUpperCase() === 'ADMIN' && (
          <Link
            href="/analytics"
            className={`w-full flex items-center space-x-2 px-2 py-2 hover:bg-purple-800 rounded text-sm mb-1 ${
              pathname === '/analytics' ? 'bg-purple-700' : ''
            }`}
          >
            <BarChart3 className="h-4 w-4" />
            <span>Analytics</span>
          </Link>
        )}
        <button
          onClick={handleLogout}
          className="w-full flex items-center space-x-2 px-2 py-2 hover:bg-purple-800 rounded text-sm"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign out</span>
        </button>
      </div>

      {/* Create Channel Modal */}
      <CreateChannelModal
        isOpen={showCreateChannelModal}
        onClose={() => setShowCreateChannelModal(false)}
        onSuccess={(channel) => {
          router.push(`/channels/${channel.id}`);
        }}
      />

      {/* Profile Modal */}
      <ProfileModal
        isOpen={showProfileModal}
        onClose={() => setShowProfileModal(false)}
      />
    </div>
  );
}
