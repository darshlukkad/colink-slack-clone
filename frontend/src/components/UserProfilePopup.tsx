'use client';

import { useQuery } from '@tanstack/react-query';
import { User } from '@/types';
import { X, Mail, Phone } from 'lucide-react';
import { authApi } from '@/lib/api';

interface UserProfilePopupProps {
  user: User;
  isOpen: boolean;
  onClose: () => void;
  position?: { x: number; y: number };
}

export function UserProfilePopup({ user, isOpen, onClose, position }: UserProfilePopupProps) {
  // Fetch complete user data to ensure we have email and phone
  const { data: fullUser, isLoading, error } = useQuery({
    queryKey: ['user-profile', user.id],
    queryFn: async () => {
      console.log('[UserProfilePopup] Fetching user data for ID:', user.id);
      const data = await authApi.get<User>(`/auth/users/${user.id}`);
      console.log('[UserProfilePopup] Fetched user data:', data);
      return data;
    },
    enabled: isOpen,
  });

  // Use fetched user data if available, otherwise fall back to passed user
  const displayUser = fullUser || user;

  console.log('[UserProfilePopup] Display user:', displayUser);
  console.log('[UserProfilePopup] Email:', displayUser.email);
  console.log('[UserProfilePopup] Phone:', displayUser.phone_number);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40 flex items-center justify-center"
        onClick={onClose}
      >
        {/* Popup */}
        <div
          className="bg-white rounded-lg shadow-xl border border-gray-200 w-96 max-w-md mx-4"
          onClick={(e) => e.stopPropagation()}
        >
        {/* Header */}
        <div className="relative p-4 border-b border-gray-200">
          <button
            onClick={onClose}
            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Profile Photo */}
          <div className="flex flex-col items-center mb-4">
            <div className="w-24 h-24 rounded-full bg-blue-500 flex items-center justify-center overflow-hidden mb-3">
              {displayUser.avatar_url ? (
                <img
                  src={displayUser.avatar_url}
                  alt={displayUser.display_name || displayUser.username}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-white text-3xl font-semibold">
                  {displayUser.display_name?.[0]?.toUpperCase() ||
                    displayUser.username?.[0]?.toUpperCase() ||
                    'U'}
                </span>
              )}
            </div>

            {/* Name */}
            <h3 className="text-xl font-semibold text-gray-900">
              {displayUser.display_name || displayUser.username}
            </h3>
            {displayUser.display_name && (
              <p className="text-sm text-gray-500">@{displayUser.username}</p>
            )}
          </div>

          {/* Info */}
          <div className="space-y-3">
            {/* Email */}
            <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-md">
              <Mail className="h-5 w-5 text-gray-500 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 mb-1">Email</p>
                <p className="text-sm text-gray-900 truncate">{displayUser.email}</p>
              </div>
            </div>

            {/* Phone */}
            <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-md">
              <Phone className="h-5 w-5 text-gray-500 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 mb-1">Phone</p>
                <p className="text-sm text-gray-900 truncate">
                  {displayUser.phone_number || 'Phone number not set'}
                </p>
              </div>
            </div>

            {/* Status Text */}
            {displayUser.status_text && (
              <div className="p-3 bg-gray-50 rounded-md">
                <p className="text-xs text-gray-500 mb-1">Status</p>
                <p className="text-sm text-gray-900">{displayUser.status_text}</p>
              </div>
            )}
          </div>
        </div>
        </div>
      </div>
    </>
  );
}
