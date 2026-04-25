import client from './client';

// 获取项目-对话树形结构（供侧边栏使用）
export function getConversationTree() {
  return client.get('/conversation/tree');
}

// 获取指定项目下的对话列表（备用）
export function getConversationsByProject(projectId) {
  return client.get('/conversation/conversations', { params: { project_id: projectId } });
}

// 创建对话
export function createConversation(data) {
  return client.post('/conversation/conversations', data);
}

// 更新对话
export function updateConversation(id, data) {
  return client.put(`/conversation/conversations/${id}`, data);
}

// 删除对话
export function deleteConversation(id) {
  return client.delete(`/conversation/conversations/${id}`);
}

// 获取对话历史消息
export function getConversationHistory(conversationId) {
  return client.get(`/conversation/history/${conversationId}`);
}

// 发送消息
export function sendMessage(data) {
  return client.post('/conversation/send', data);
}