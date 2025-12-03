'use client';

import { useState, useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { authApi, filesApi } from '@/lib/api';
import { User } from '@/types';
import { X, Pencil, Loader2 } from 'lucide-react';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ProfileModal({ isOpen, onClose }: ProfileModalProps) {
  const queryClient = useQueryClient();
  const { user, setUser } = useAuthStore();

  const [displayName, setDisplayName] = useState(user?.display_name || '');
  const [phoneNumber, setPhoneNumber] = useState(user?.phone_number || '');
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url || '');
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sync state with user data when modal opens or user changes
  useEffect(() => {
    if (isOpen && user) {
      setDisplayName(user.display_name || '');
      setPhoneNumber(user.phone_number || '');
      setAvatarUrl(user.avatar_url || '');
      setAvatarFile(null);
      setAvatarPreview(null);
      setIsEditing(false);
    }
  }, [isOpen, user]);

  const updateProfileMutation = useMutation({
    mutationFn: async (updates: Partial<User>) => {
      const response = await authApi.patch<User>('/auth/me', updates);
      return response;
    },
    onSuccess: (updatedUser) => {
      setUser(updatedUser);
      queryClient.invalidateQueries({ queryKey: ['user'] });
      setIsEditing(false);
      setAvatarFile(null);
      setAvatarPreview(null);
    },
    onError: (error) => {
      console.error('Failed to update profile:', error);
      alert('Failed to update profile. Please try again.');
    },
  });

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        alert('Please select an image file');
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        alert('File size must be less than 5MB');
        return;
      }

      setAvatarFile(file);

      // Create preview URL
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handlePhotoClick = () => {
    if (isEditing) {
      fileInputRef.current?.click();
    }
  };

  const handleSave = async () => {
    try {
      let uploadedAvatarUrl = avatarUrl;

      // If user selected a new avatar file, upload it first
      if (avatarFile) {
        const formData = new FormData();
        formData.append('file', avatarFile);

        // Upload to files service (note: files service uses /api/v1 prefix)
        const uploadResponse = await filesApi.post<{ url: string }>('/api/v1/files/upload', formData);

        uploadedAvatarUrl = uploadResponse.url;
      }

      // Update profile with new data
      updateProfileMutation.mutate({
        display_name: displayName,
        phone_number: phoneNumber,
        avatar_url: uploadedAvatarUrl,
      });
    } catch (error) {
      console.error('Failed to upload avatar:', error);
      alert('Failed to upload photo. Please try again.');
    }
  };

  const handleCancel = () => {
    setDisplayName(user?.display_name || '');
    setPhoneNumber(user?.phone_number || '');
    setAvatarUrl(user?.avatar_url || '');
    setAvatarFile(null);
    setAvatarPreview(null);
    setIsEditing(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold text-gray-900">Profile</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Profile Photo */}
          <div className="flex flex-col items-center space-y-2">
            <div className="relative">
              <button
                onClick={handlePhotoClick}
                disabled={!isEditing}
                className={`w-24 h-24 rounded-full bg-purple-600 flex items-center justify-center text-white text-3xl font-semibold overflow-hidden ${
                  isEditing ? 'cursor-pointer' : 'cursor-default'
                }`}
              >
                {avatarPreview ? (
                  <img src={avatarPreview} alt="Profile Preview" className="w-full h-full object-cover" />
                ) : avatarUrl ? (
                  <img src={avatarUrl} alt="Profile" className="w-full h-full object-cover" />
                ) : (
                  <span>
                    {displayName?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
                  </span>
                )}
              </button>
              {isEditing && (
                <div
                  onClick={handlePhotoClick}
                  className="absolute bottom-0 right-0 bg-purple-600 text-white p-2 rounded-full hover:bg-purple-700 transition-colors cursor-pointer"
                  title="Change photo"
                >
                  <Pencil className="h-4 w-4" />
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
            {isEditing && avatarFile && (
              <p className="text-xs text-gray-600">
                Selected: {avatarFile.name}
              </p>
            )}
          </div>

          {/* Display Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Display Name
            </label>
            {isEditing ? (
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full px-3 py-2 text-gray-900 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="Enter your display name"
              />
            ) : (
              <div className="px-3 py-2 bg-gray-50 rounded-md text-gray-900">
                {displayName || user?.display_name || user?.username || 'Not set'}
              </div>
            )}
          </div>

          {/* Username (non-editable) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Username
            </label>
            <div className="px-3 py-2 bg-gray-50 rounded-md text-gray-900">
              @{user?.username}
            </div>
          </div>

          {/* Email (non-editable) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <div className="px-3 py-2 bg-gray-50 rounded-md text-gray-900">
              {user?.email}
            </div>
          </div>

          {/* Phone Number */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Phone Number
            </label>
            {isEditing ? (
              <input
                type="tel"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="w-full px-3 py-2 text-gray-900 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="Enter your phone number"
              />
            ) : (
              <div className="px-3 py-2 bg-gray-50 rounded-md text-gray-900">
                {user?.phone_number || 'Not set'}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t bg-gray-50">
          {isEditing ? (
            <>
              <button
                onClick={handleCancel}
                disabled={updateProfileMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={updateProfileMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {updateProfileMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Save Changes
              </button>
            </>
          ) : (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 transition-colors"
              >
                Edit Profile
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
