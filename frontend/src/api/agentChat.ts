/**
 * Agent Chat API — 智能体对话接口
 * 支持 SSE 流式对话和普通 JSON 对话
 */

import client from './client';

// ── 消息类型 ──

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  createdAt: string
  toolCalls?: ToolCall[]
  toolResults?: ToolResult[]
}

export interface ToolCall {
  name: string
  args: Record<string, unknown>
  id: string
}

export interface ToolResult {
  name: string
  content: string
  success: boolean
}

// ── SSE 事件类型 ──

export interface SSEEvent {
  type: 'status' | 'tool_call' | 'tool_result' | 'start_response' | 'response_chunk' | 'done' | 'error'
  data: string | ToolCallData
  conversation_id: string
}

export interface ToolCallData {
  name: string
  args: Record<string, unknown>
  id: string
}

// ── SSE 流式对话 ──

/**
 * 通过 SSE 流式调用 Agent 对话
 * 
 * @param content 用户输入
 * @param conversationId 可选的对话 ID
 * @param onEvent 事件回调
 * @returns AbortController，用于取消请求
 */
export function streamChat(
  content: string,
  conversationId?: string,
  onEvent?: (event: SSEEvent) => void,
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem('nova_token');

  fetch('/api/v1/agent/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      content,
      conversation_id: conversationId || null,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        onEvent?.({
          type: 'error',
          data: `请求失败 (${response.status}): ${errText}`,
          conversation_id: conversationId || '',
        });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onEvent?.({
          type: 'error',
          data: '无法读取响应流',
          conversation_id: conversationId || '',
        });
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 解析 SSE 事件流（data: {...}\n\n）
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // 保留最后一个不完整的数据块

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6);
              const event = JSON.parse(jsonStr) as SSEEvent;
              onEvent?.(event);
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onEvent?.({
          type: 'error',
          data: `连接错误: ${err.message}`,
          conversation_id: conversationId || '',
        });
      }
    });

  return controller;
}

// ── 普通 JSON 对话 ──

export interface ChatResponse {
  reply: string
  conversation_id: string
}

/**
 * 非流式对话接口
 */
export async function sendChat(content: string, conversationId?: string): Promise<ChatResponse> {
  const res = await client.post('/agent/chat', {
    content,
    conversation_id: conversationId || null,
  });
  return res as unknown as ChatResponse;
}