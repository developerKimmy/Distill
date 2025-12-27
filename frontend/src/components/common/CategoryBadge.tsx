import { getCategoryColors } from '../../utils/constants';

interface CategoryBadgeProps {
  category: string | null | undefined;
  variant?: 'badge' | 'dot' | 'solid';
  size?: 'sm' | 'md';
}

export function CategoryBadge({ category, variant = 'badge', size = 'md' }: CategoryBadgeProps) {
  const colors = getCategoryColors(category);
  const displayName = category || '기타';

  if (variant === 'dot') {
    return (
      <span className="flex items-center gap-1.5">
        <span className={`w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-sm ${colors.dot}`} />
        <span className={size === 'sm' ? 'text-xs' : 'text-sm'}>{displayName}</span>
      </span>
    );
  }

  if (variant === 'solid') {
    return (
      <span className={`${colors.bg} ${colors.text} px-2 py-0.5 rounded text-xs sm:text-sm`}>
        {displayName}
      </span>
    );
  }

  return (
    <span className={`${colors.badge} px-2 py-1 rounded-full text-xs sm:text-sm font-medium`}>
      {displayName}
    </span>
  );
}
