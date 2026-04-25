import client from './client';
import type { PriorityItem } from '@/types';

/**
 * 获取单个优先级事项详情
 * @param id - 事项ID
 */
export function getPriority(id: string | number): Promise<{ priority: PriorityItem }> {
  return client.get(`/priority/${id}`);
}

/**
 * 更新优先级事项
 * @param id - 事项ID
 * @param data - 更新数据
 */
export function updatePriority(id: string | number, data: Partial<PriorityItem>): Promise<{ priority: PriorityItem }> {
  return client.put(`/priority/${id}`, data);
}

/**
 * 删除优先级事项
 * @param id - 事项ID
 */
export function deletePriority(id: string | number): Promise<unknown> {
  return client.delete(`/priority/${id}`);
}

/**
 * 获取优先级事项列表
 * @param params - { page, limit, status }
 */
export function getPriorities(params: Record<string, unknown> = {}): Promise<{ items: PriorityItem[]; total: number }> {
  return client.get('/priority', { params });
}
