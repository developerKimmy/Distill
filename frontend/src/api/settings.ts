import client from './client';
import type { NotificationSettings } from '../types';

// 알림 설정 조회
export const getNotificationSettings = async (): Promise<NotificationSettings> => {
  const { data } = await client.get('/settings/notifications');
  return data;
};

// 알림 설정 수정
export const updateNotificationSettings = async (
  settings: { enabled?: boolean; times?: string[] }
): Promise<NotificationSettings> => {
  const { data } = await client.put('/settings/notifications', settings);
  return data;
};
