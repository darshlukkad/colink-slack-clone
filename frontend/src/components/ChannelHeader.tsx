'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { channelApi, authApi } from '@/lib/api';
import { Channel, User } from '@/types';
import { Hash, Lock, Users, Star, Info, MoreVertical, Trash2, Search, Sun, Moon } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useThemeStore } from '@/store/themeStore';
import { OnlineStatus } from './OnlineStatus';

interface ChannelHeaderProps {
  channel: Channel;
  onSearch?: (query: string) => void;
}

interface ChannelMember {
  user_id: string;
  username: string;
  display_name?: string;
  is_admin: boolean;
  notifications_enabled: boolean;
  created_at: string;
}

export function ChannelHeader({ channel, onSearch }: ChannelHeaderProps) {
  const { user } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isPrivate = channel.channel_type === 'PRIVATE';
  const isDirect = channel.channel_type === 'DIRECT';
  const [showMembersTooltip, setShowMembersTooltip] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  const [showSearchBox, setShowSearchBox] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch channel members
  const { data: membersData } = useQuery({
    queryKey: ['channel-members', channel.id],
    queryFn: async () => {
      return await channelApi.get<{ members: ChannelMember[]; total: number }>(
        `/channels/${channel.id}/members`
      );
    },
  });

  // Get the other user's ID for DM channels
  const otherUserId = isDirect && membersData?.members
    ? membersData.members.find((member) => member.user_id !== user?.id)?.user_id
    : null;

  // Fetch complete user profile for DM channels
  const { data: otherUserProfile } = useQuery({
    queryKey: ['user-profile', otherUserId],
    queryFn: async () => {
      if (!otherUserId) return null;
      return await authApi.get<User>(`/auth/users/${otherUserId}`);
    },
    enabled: isDirect && !!otherUserId,
  });

  // For direct messages, get the other person's name from members
  const getDisplayName = () => {
    if (!isDirect) return channel.name;

    // Get the other user from members
    if (membersData?.members) {
      const otherMember = membersData.members.find(
        (member) => member.user_id !== user?.id
      );
      if (otherMember) {
        return otherMember.display_name || otherMember.username;
      }
    }

    // Fallback to channel name
    return channel.name;
  };

  const displayName = getDisplayName();

  // Check if current user is channel admin
  const isChannelAdmin = membersData?.members.find(
    (member) => member.user_id === user?.id
  )?.is_admin || false;

  // Delete channel mutation
  const deleteChannelMutation = useMutation({
    mutationFn: async () => {
      return await channelApi.delete(`/channels/${channel.id}`);
    },
    onSuccess: () => {
      // Invalidate channels query to refresh the list
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      // Navigate to home or first available channel
      router.push('/channels');
    },
    onError: (error: any) => {
      console.error('Failed to delete channel:', error);
      alert(error.response?.data?.detail || 'Failed to delete channel. Please try again.');
    },
  });

  const handleDeleteChannel = () => {
    if (confirm(`Are you sure you want to delete the channel "${channel.name}"? This action cannot be undone.`)) {
      deleteChannelMutation.mutate();
    }
  };

  const handleSearch = () => {
    if (searchQuery.trim() && onSearch) {
      onSearch(searchQuery.trim());
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    if (onSearch) {
      onSearch(''); // Clear the search
    }
    setShowSearchBox(false);
  };

  return (
    <div className="h-14 border-b border-gray-200 px-4 flex items-center justify-between bg-white">
      <div className="flex items-center space-x-2">
        {isDirect ? (
          <div className="relative flex-shrink-0">
            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center overflow-hidden">
              {otherUserProfile?.avatar_url ? (
                <img
                  src={otherUserProfile.avatar_url}
                  alt={otherUserProfile.display_name || otherUserProfile.username}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-white text-sm font-medium">
                  {otherUserProfile?.display_name?.[0]?.toUpperCase() ||
                    otherUserProfile?.username?.[0]?.toUpperCase() ||
                    displayName?.[0]?.toUpperCase() ||
                    'U'}
                </span>
              )}
            </div>
            {/* Online status dot positioned at bottom-right of avatar */}
            {otherUserProfile?.keycloak_id && (
              <div className="absolute -bottom-0.5 -right-0.5">
                <OnlineStatus userId={otherUserProfile.keycloak_id} className="w-3 h-3 border-2 border-white" />
              </div>
            )}
          </div>
        ) : isPrivate ? (
          <Lock className="h-5 w-5 text-gray-600" />
        ) : (
          <Hash className="h-5 w-5 text-gray-600" />
        )}
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{displayName}</h2>
          {!isDirect && channel.topic && (
            <p className="text-xs text-gray-500 truncate max-w-md">{channel.topic}</p>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-2">
        {/* Theme Toggle Button */}
        <button
          onClick={() => {
            console.log('Theme toggle clicked, current theme:', theme);
            toggleTheme();
          }}
          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? (
            <Moon className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          ) : (
            <Sun className="h-5 w-5 text-yellow-500" />
          )}
        </button>

        {/* Search Button */}
        <div className="relative">
          <button
            onClick={() => setShowSearchBox(!showSearchBox)}
            className="p-2 hover:bg-gray-100 rounded"
          >
            <Search className="h-5 w-5 text-gray-600" />
          </button>

          {/* Search Box Tooltip */}
          {showSearchBox && (
            <>
              {/* Backdrop to close search when clicking outside */}
              <div
                className="fixed inset-0 z-10"
                onClick={handleClearSearch}
              />

              {/* Search input tooltip */}
              <div className="absolute right-0 top-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-3 min-w-[300px] z-20">
                <div className="text-xs font-semibold text-gray-700 mb-2">
                  SEARCH IN THIS CHAT
                </div>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    placeholder="Search messages..."
                    className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 text-sm"
                    autoFocus
                  />
                </div>
                {searchQuery && (
                  <div className="mt-2 text-xs text-gray-500">
                    Press Enter to search for "{searchQuery}"
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <button className="p-2 hover:bg-gray-100 rounded">
          <Star className="h-5 w-5 text-gray-600" />
        </button>
        <div className="relative">
          <button
            className="p-2 hover:bg-gray-100 rounded flex items-center space-x-1"
            onMouseEnter={() => setShowMembersTooltip(true)}
            onMouseLeave={() => setShowMembersTooltip(false)}
          >
            <Users className="h-5 w-5 text-gray-600" />
            {channel.member_count && (
              <span className="text-sm text-gray-600">{channel.member_count}</span>
            )}
          </button>
          {showMembersTooltip && membersData?.members && (
            <div className="absolute right-0 top-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-3 min-w-[200px] z-50">
              <div className="text-xs font-semibold text-gray-700 mb-2">
                MEMBERS ({membersData.total})
              </div>
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {membersData.members.map((member) => (
                  <div
                    key={member.user_id}
                    className="flex items-center space-x-2 py-1"
                  >
                    <div className="w-6 h-6 rounded bg-blue-500 flex items-center justify-center flex-shrink-0">
                      <span className="text-white text-xs font-medium">
                        {(member.display_name?.[0] || member.username?.[0])?.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-900 truncate">
                        {member.display_name || member.username}
                        {member.user_id === user?.id && (
                          <span className="text-xs text-gray-500"> (you)</span>
                        )}
                      </div>
                      {member.is_admin && (
                        <div className="text-xs text-gray-500">Admin</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <button className="p-2 hover:bg-gray-100 rounded">
          <Info className="h-5 w-5 text-gray-600" />
        </button>

        {/* Options menu for admins (not shown for DM channels) */}
        {!isDirect && isChannelAdmin && (
          <div className="relative">
            <button
              onClick={() => setShowOptionsMenu(!showOptionsMenu)}
              className="p-2 hover:bg-gray-100 rounded"
            >
              <MoreVertical className="h-5 w-5 text-gray-600" />
            </button>

            {showOptionsMenu && (
              <>
                {/* Backdrop to close menu when clicking outside */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowOptionsMenu(false)}
                />

                {/* Dropdown menu */}
                <div className="absolute right-0 top-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[180px] z-20">
                  <button
                    onClick={() => {
                      setShowOptionsMenu(false);
                      handleDeleteChannel();
                    }}
                    disabled={deleteChannelMutation.isPending}
                    className="w-full flex items-center space-x-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="h-4 w-4" />
                    <span>{deleteChannelMutation.isPending ? 'Deleting...' : 'Delete Channel'}</span>
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
