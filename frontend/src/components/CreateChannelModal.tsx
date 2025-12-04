'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { channelApi, authApi } from '@/lib/api';
import { User, Channel } from '@/types';
import { X, Hash, Lock, Search } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';

interface CreateChannelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (channel: Channel) => void;
}

export function CreateChannelModal({ isOpen, onClose, onSuccess }: CreateChannelModalProps) {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const [step, setStep] = useState<'details' | 'members'>('details');
  const [channelName, setChannelName] = useState('');
  const [description, setDescription] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch all users
  const { data: allUsers = [] } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const data = await authApi.get<User[]>('/auth/users');
      return Array.isArray(data) ? data : [];
    },
    enabled: isOpen && step === 'members',
  });

  // Filter users based on search and exclude current user and admin users
  const filteredUsers = allUsers.filter(
    (u) =>
      u.id !== currentUser?.id && // Exclude current user
      u.role?.toLowerCase() !== 'admin' && // Exclude admin users
      (u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.display_name?.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const createChannelMutation = useMutation({
    mutationFn: async (data: { name: string; description?: string; channel_type: string }) => {
      return await channelApi.post<Channel>('/channels', data);
    },
    onSuccess: async (channel) => {
      // Add members to the channel if any selected
      // Filter out the current user since they're automatically added when creating the channel
      const membersToAdd = selectedUserIds.filter(userId => userId !== currentUser?.id);

      if (membersToAdd.length > 0) {
        try {
          // Add members sequentially to avoid race conditions
          for (const userId of membersToAdd) {
            try {
              await channelApi.post(`/channels/${channel.id}/members`, { user_id: userId });
            } catch (error: any) {
              // Ignore 409 errors (user already a member) but log other errors
              if (error.response?.status !== 409) {
                console.error(`Error adding member ${userId}:`, error);
              }
            }
          }
        } catch (error) {
          console.error('Error adding members:', error);
        }
      }

      queryClient.invalidateQueries({ queryKey: ['channels'] });
      onSuccess?.(channel);
      handleClose();
    },
    onError: (error: any) => {
      console.error('Failed to create channel:', error);
      alert(error.response?.data?.detail || 'Failed to create channel');
    },
  });

  const handleClose = () => {
    setStep('details');
    setChannelName('');
    setDescription('');
    setIsPrivate(false);
    setSelectedUserIds([]);
    setSearchQuery('');
    onClose();
  };

  const handleNext = () => {
    if (step === 'details') {
      if (!channelName.trim()) {
        alert('Channel name is required');
        return;
      }
      setStep('members');
    }
  };

  const handleCreate = () => {
    createChannelMutation.mutate({
      name: channelName.trim(),
      description: description.trim() || undefined,
      channel_type: isPrivate ? 'PRIVATE' : 'PUBLIC',
    });
  };

  const toggleUserSelection = (userId: string) => {
    setSelectedUserIds((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            {step === 'details' ? 'Create a channel' : 'Add members'}
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4">
          {step === 'details' ? (
            <div className="space-y-4">
              {/* Channel Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Channel name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    {isPrivate ? <Lock className="h-4 w-4" /> : <Hash className="h-4 w-4" />}
                  </div>
                  <input
                    type="text"
                    value={channelName}
                    onChange={(e) => setChannelName(e.target.value)}
                    placeholder="e.g. marketing"
                    className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900"
                    maxLength={80}
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Names must be lowercase, without spaces or periods, and can't be longer than 80
                  characters.
                </p>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (optional)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What's this channel about?"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none text-gray-900"
                  maxLength={250}
                />
              </div>

              {/* Privacy Toggle */}
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                <div className="flex-1">
                  <div className="font-medium text-gray-900">Make private</div>
                  <div className="text-sm text-gray-500">
                    {isPrivate
                      ? 'Only invited members can see this channel'
                      : 'Anyone can join this channel'}
                  </div>
                </div>
                <button
                  onClick={() => setIsPrivate(!isPrivate)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    isPrivate ? 'bg-purple-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      isPrivate ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search members..."
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Selected count */}
              <div className="text-sm text-gray-600">
                {selectedUserIds.length} member{selectedUserIds.length !== 1 ? 's' : ''} selected
              </div>

              {/* User list */}
              <div className="max-h-80 overflow-y-auto space-y-1">
                {filteredUsers.map((user) => {
                  const isSelected = selectedUserIds.includes(user.id);
                  return (
                    <button
                      key={user.id}
                      onClick={() => toggleUserSelection(user.id)}
                      className={`w-full flex items-center space-x-3 p-2 rounded-md hover:bg-gray-100 transition-colors ${
                        isSelected ? 'bg-purple-50' : ''
                      }`}
                    >
                      <div className="w-8 h-8 rounded bg-blue-500 flex items-center justify-center flex-shrink-0 overflow-hidden">
                        {user.avatar_url ? (
                          <img
                            src={user.avatar_url}
                            alt={user.display_name || user.username}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <span className="text-white text-sm font-medium">
                            {(user.display_name?.[0] || user.username?.[0])?.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <div className="flex-1 text-left min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {user.display_name || user.username}
                        </div>
                        <div className="text-xs text-gray-500 truncate">@{user.username}</div>
                      </div>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="h-4 w-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                      />
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-4 border-t bg-gray-50">
          {step === 'members' && (
            <button
              onClick={() => setStep('details')}
              className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-md transition-colors"
            >
              Back
            </button>
          )}
          <button
            onClick={handleClose}
            className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-md transition-colors"
          >
            Cancel
          </button>
          {step === 'details' ? (
            <button
              onClick={handleNext}
              disabled={!channelName.trim()}
              className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleCreate}
              disabled={createChannelMutation.isPending}
              className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {createChannelMutation.isPending ? 'Creating...' : 'Create'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
