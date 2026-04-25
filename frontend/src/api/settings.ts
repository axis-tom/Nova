import client from './client';
import type { SettingsResponse, NotificationResponse } from '@/types';

/**
 * 获取用户设置
 */
export function getSettings(): Promise<SettingsResponse> {
  return client.get('/settings');
}

/**
 * 更新用户设置
 * @param data - 要更新的设置字段
 */
export function updateSettings(data: Record<string, unknown>): Promise<SettingsResponse> {
  return client.put('/settings', data);
}

/**
 * 获取通知偏好
 */
export function getNotificationPreferences(): Promise<NotificationResponse> {
  return client.get('/settings/notifications');
}

/**
 * 更新通知偏好
 * @param data - 通知偏好数据
 */
export function updateNotificationPreferences(data: Record<string, unknown>): Promise<unknown> {
  return client.put('/settings/notifications', data);
}

/**
 * 获取个人资料
 */
export function getProfile(): Promise<{ profile: Record<string, unknown> }> {
  return client.get('/settings/profile');
}

/**
 * 更新个人资料
 * @param data - { name, avatar, ... }
 */
export function updateProfile(data: Record<string, unknown>): Promise<unknown> {
  return client.put('/settings/profile', data);
}

export const getCurrentUser = getProfile; // 别名导出
