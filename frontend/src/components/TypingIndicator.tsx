'use client';

interface TypingIndicatorProps {
  usernames: string[];
}

export function TypingIndicator({ usernames }: TypingIndicatorProps) {
  if (usernames.length === 0) return null;

  const displayText =
    usernames.length === 1
      ? `${usernames[0]} is typing...`
      : usernames.length === 2
      ? `${usernames[0]} and ${usernames[1]} are typing...`
      : `${usernames[0]}, ${usernames[1]}, and ${usernames.length - 2} other${
          usernames.length - 2 > 1 ? 's' : ''
        } are typing...`;

  return (
    <div className="px-4 py-2 text-sm text-gray-500 italic flex items-center space-x-2">
      <div className="flex space-x-1">
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
      </div>
      <span>{displayText}</span>
    </div>
  );
}
