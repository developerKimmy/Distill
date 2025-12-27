// Category colors for consistent styling across the app
export const CATEGORY_COLORS = {
  정치: { bg: 'bg-rose-600', text: 'text-white', badge: 'bg-rose-100 text-rose-800', dot: 'bg-rose-600' },
  경제: { bg: 'bg-amber-500', text: 'text-white', badge: 'bg-amber-100 text-amber-800', dot: 'bg-amber-500' },
  사회: { bg: 'bg-teal-500', text: 'text-white', badge: 'bg-teal-100 text-teal-800', dot: 'bg-teal-500' },
  세계: { bg: 'bg-blue-500', text: 'text-white', badge: 'bg-blue-100 text-blue-800', dot: 'bg-blue-500' },
  연예: { bg: 'bg-pink-500', text: 'text-white', badge: 'bg-pink-100 text-pink-800', dot: 'bg-pink-500' },
  'IT/과학': { bg: 'bg-violet-600', text: 'text-white', badge: 'bg-violet-100 text-violet-800', dot: 'bg-violet-600' },
  기타: { bg: 'bg-gray-500', text: 'text-white', badge: 'bg-gray-100 text-gray-800', dot: 'bg-gray-500' },
} as const;

export type CategoryName = keyof typeof CATEGORY_COLORS;

export const AVAILABLE_CATEGORIES: CategoryName[] = ['정치', '경제', '사회', '세계', '연예', 'IT/과학'];

export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'] as const;

export const getCategoryColors = (category: string | null | undefined) => {
  return CATEGORY_COLORS[category as CategoryName] || CATEGORY_COLORS['기타'];
};
