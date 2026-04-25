import client from './client';
import type { BriefingListResponse, GenerateBriefingParams, GenerateBriefingResponse, BriefingTaskStatus } from '@/types';

/**
 * 获取简报列表（支持分页）
 * @param params - { page, limit, sort }
 */
export function getBriefings(params: Record<string, unknown> = {}): Promise<BriefingListResponse> {
  // 将前端常用的 page/limit 转换为后端需要的 skip/limit
  let { page, limit, skip, ...rest } = params as { page?: number; limit?: number; skip?: number; [key: string]: unknown };

  // 如果传入了 page 和 limit，则自动计算 skip
  if (page !== undefined && limit !== undefined) {
    skip = (page - 1) * limit;
    // 保留 limit 用于后端
  } else if (skip === undefined) {
    skip = 0;
  }
  if (limit === undefined) limit = 10;

  // 使用带斜杠的 URL，避免重定向丢失认证头
  return client.get('/briefings/', { params: { skip, limit, ...rest } });
}

/**
 * 获取单个简报详情
 * @param id - 简报ID
 */
export function getBriefing(id: string | number): Promise<{ briefing: import('@/types').Briefing }> {
  return client.get(`/briefings/${id}`);
}

/**
 * 生成新的简报（异步任务，返回 task_id 或直接返回结果）
 * @param data - 生成参数（如时间范围、数据源等）
 */
export function generateBriefing(data: GenerateBriefingParams): Promise<GenerateBriefingResponse> {
  return client.post('/briefings/generate', data);
}

/**
 * 删除简报
 * @param id - 简报ID
 */
export function deleteBriefing(id: string | number): Promise<unknown> {
  return client.delete(`/briefings/${id}`);
}

/**
 * 获取简报生成任务状态（若生成是异步的）
 * @param taskId - 任务ID
 */
export function getBriefingTaskStatus(taskId: string): Promise<BriefingTaskStatus> {
  return client.get(`/briefings/tasks/${taskId}`);
}
