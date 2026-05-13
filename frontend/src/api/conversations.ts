import client from './client';
import type { Conversation } from '@/types';

// 获取项目-对话树形结构（供侧边栏使用）
export function getConversationTree(): Promise<{ tree: unknown[] }> {
  return client.get('/conversation/tree');
}

// 获取指定项目下的对话列表（备用）
export function getConversationsByProject(projectId: string | number): Promise<{ conversations: Conversation[] }> {
  return client.get('/conversation/conversations', { params: { project_id: projectId } });
}

// 创建对话
export function createConversation(data: Partial<Conversation>): Promise<{ conversation: Conversation }> {
  return client.post('/conversation/conversations', data);
}

// 更新对话
export function updateConversation(id: string | number, data: Partial<Conversation>): Promise<{ conversation: Conversation }> {
  return client.put(`/conversation/conversations/${id}`, data);
}

// 删除对话
export function deleteConversation(id: string | number): Promise<unknown> {
  return client.delete(`/conversation/conversations/${id}`);
}

// 获取对话历史消息
export function getConversationHistory(conversationId: string | number): Promise<{ messages: import('@/types').Message[] }> {
  return client.get(`/conversation/history/${conversationId}`);
}

// 发送消息
export function sendMessage(data: { conversationId?: string | number; content: string; role?: string }): Promise<{ reply: import('@/types').Message }> {
  return client.post('/conversation/send', data);
}
