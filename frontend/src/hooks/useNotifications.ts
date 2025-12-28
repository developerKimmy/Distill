import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getNotifications, getUnreadCount, markAsRead, markAllAsRead } from '../api/notifications';

export const NOTIFICATIONS_KEY = ['notifications'];
export const UNREAD_COUNT_KEY = ['notifications', 'unread-count'];

export function useNotifications(page = 1, size = 20, unreadOnly = false) {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, { page, size, unreadOnly }],
    queryFn: () => getNotifications(page, size, unreadOnly),
    staleTime: 30 * 1000, // 30초
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: UNREAD_COUNT_KEY,
    queryFn: getUnreadCount,
    staleTime: 30 * 1000, // 30초
    refetchInterval: 60 * 1000, // 1분마다 폴링
  });
}

export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
      queryClient.invalidateQueries({ queryKey: UNREAD_COUNT_KEY });
    },
  });
}

export function useMarkAllAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
      queryClient.invalidateQueries({ queryKey: UNREAD_COUNT_KEY });
    },
  });
}
