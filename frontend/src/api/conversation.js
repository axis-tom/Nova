import client from './client';

/**
 * 获取对话历史列表
 * @param {Object} params - { page, limit }
 * @returns {Promise} { conversations: [], total }
 */
export function getConversations(params = {}) {
  return client.get('/conversations', { params });
}

/**
 * 获取单个对话的完整消息记录
 * @param {string|number} conversationId
 * @returns {Promise} { messages: [] }
 */
export function getConversationMessages(conversationId) {
  return client.get(`/conversations/${conversationId}/messages`);
}

/**
 * 发送消息（普通 HTTP 方式，若使用 WebSocket 则需单独处理）
 * @param {Object} data - { conversationId, content, attachments? }
 * @returns {Promise} { message }
 */
export function sendMessage(data) {
  return client.post('/conversations/message', data);
}

/**
 * 删除对话
 * @param {string|number} conversationId
 * @returns {Promise}
 */
export function deleteConversation(conversationId) {
  return client.delete(`/conversations/${conversationId}`);
}

/**
 * 清除所有对话（谨慎使用）
 * @returns {Promise}
 */
export function clearAllConversations() {
  return client.delete('/conversations/all');
}

