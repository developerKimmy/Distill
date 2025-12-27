interface FollowButtonProps {
  isFollowing: boolean;
  onClick: (e: React.MouseEvent) => void;
  variant?: 'icon' | 'full';
  disabled?: boolean;
}

export function FollowButton({
  isFollowing,
  onClick,
  variant = 'icon',
  disabled = false,
}: FollowButtonProps) {
  if (variant === 'full') {
    return (
      <button
        onClick={onClick}
        disabled={disabled}
        className={`
          shrink-0 flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors w-full sm:w-auto
          ${isFollowing
            ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            : 'bg-amber-500 text-white hover:bg-amber-600'
          }
          disabled:opacity-50
        `}
      >
        {isFollowing ? (
          <>
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
            </svg>
            팔로우 중
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            팔로우
          </>
        )}
      </button>
    );
  }

  // Icon variant (default)
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        p-1.5 rounded-full transition-colors
        ${isFollowing
          ? 'bg-amber-100 text-amber-600 hover:bg-amber-200'
          : 'bg-gray-100 text-gray-400 hover:bg-gray-200 hover:text-gray-600'
        }
        disabled:opacity-50
      `}
      title={isFollowing ? '팔로우 중' : '팔로우'}
    >
      <svg
        className="w-4 h-4"
        fill={isFollowing ? 'currentColor' : 'none'}
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
        />
      </svg>
    </button>
  );
}
