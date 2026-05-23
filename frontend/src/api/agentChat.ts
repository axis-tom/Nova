/**
 * Agent Chat API — 智能体对话接口
 * 支持 SSE 流式对话、普通 JSON 对话、会话管理
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
  type: 'status' | 'tool_call' | 'tool_result' | 'start_response' | 'response_chunk' | 'done' | 'error' | 'agent_start' | 'agent_end' | 'briefing_data' | 'tree_node_status' | 'tree_node_added' | 'tree_full'
  data: string | ToolCallData | TreeNodeStatusData | TreeNodeAddedData | TreeFullData
  conversation_id: string
}

export interface ToolCallData {
  name: string
  args: Record<string, unknown>
  id: string
}

// ── 分析树类型 ──

export interface TreeNodeStatusData {
  invocation_id: string
  agent_name: string
  branch_label: string
  status: 'running' | 'completed' | 'error'
  dimensions: string[]
}

export interface TreeNodeAddedData {
  invocation_id: string
  agent_name: string
  branch_label: string
  parent_invocation_id: string | null
  dimensions: string[]
  status: 'completed' | 'error'
  result_summary: string
  checkpoint_id: string | null
  conversation_round: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface TreeInvocation {
  invocation_id: string
  agent_name: string
  branch_label: string
  params: Record<string, unknown>
  dimensions: string[]
  result_summary: string
  status: 'running' | 'completed' | 'error'
  parent_invocation_id: string | null
  checkpoint_id: string | null
  conversation_round: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface TreeBranchData {
  branch_id: string
  agent_name: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'error' | 'partial'
  invocations: TreeInvocation[]
}

export interface TreeFullData {
  conversation_id: string
  conversation_round: number
  branches: TreeBranchData[]
}

export interface TreeResponse {
  conversation_id: string
  tree: TreeFullData | null
  checkpoints: any[]
}

export interface BacktrackResponse {
  ok: boolean
  invocation_id: string
  agent_name: string
  branch_label: string
  checkpoint_id: string | null
  restored_state_keys: string[]
  message: string
}

export interface AppendDimensionResponse {
  ok: boolean
  agent_name: string
  dimension_label: string
  checkpoint_id: string | null
  restored_state_keys: string[]
  message: string
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

// ── 会话管理 ──

export interface ConversationItem {
  id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ConversationMessages {
  conversation_id: string
  title: string
  messages: Array<{
    id: number
    role: string
    content: string
    metadata: Record<string, unknown> | null
    created_at: string
  }>
}

export async function getConversations(): Promise<ConversationItem[]> {
  const res = await client.get('/agent/conversations');
  return res as unknown as ConversationItem[];
}

export async function getConversationMessages(convId: string): Promise<ConversationMessages> {
  const res = await client.get(`/agent/conversations/${convId}/messages`);
  return res as unknown as ConversationMessages;
}

export async function renameConversation(convId: string, title: string): Promise<void> {
  await client.put(`/agent/conversations/${convId}`, { title });
}

export async function deleteConversation(convId: string): Promise<void> {
  await client.delete(`/agent/conversations/${convId}`);
}

// ── 分析树操作 ──

/** 获取分析树 */
export async function getAnalysisTree(convId: string): Promise<TreeResponse> {
  const res = await client.get(`/agent/conversations/${convId}/tree`);
  return res as unknown as TreeResponse;
}

/** 回溯到指定 invocation */
export async function backtrackAnalysis(convId: string, invocationId: string): Promise<BacktrackResponse> {
  const res = await client.post(`/agent/conversations/${convId}/tree/backtrack`, {
    invocation_id: invocationId,
  });
  return res as unknown as BacktrackResponse;
}

/** 追加分析维度 */
export async function appendDimension(
  convId: string,
  agentName: string,
  dimensionLabel: string,
  dimensionParams: Record<string, unknown> = {},
): Promise<AppendDimensionResponse> {
  const res = await client.post(`/agent/conversations/${convId}/tree/append_dimension`, {
    agent_name: agentName,
    dimension_label: dimensionLabel,
    dimension_params: dimensionParams,
  });
  return res as unknown as AppendDimensionResponse;
}