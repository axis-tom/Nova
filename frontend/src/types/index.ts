// ===== 公共类型定义 =====

// 用户相关
export interface User {
  id: string
  name: string
  email: string
  avatar?: string
}

export interface AuthResponse {
  token: string
  user: User
}

// 简报相关
export interface Briefing {
  id: string
  title: string
  content: string
  type: string
  status: 'draft' | 'completed' | 'failed'
  createdAt: string
  updatedAt: string
  metadata?: Record<string, unknown>
}

export interface BriefingListResponse {
  items: Briefing[]
  total: number
  page: number
  limit: number
}

export interface GenerateBriefingParams {
  type?: string
  template?: string
  [key: string]: unknown
}

export interface GenerateBriefingResponse {
  taskId?: string
  briefing?: Briefing
}

export interface BriefingTaskStatus {
  status: 'pending' | 'running' | 'completed' | 'failed'
  briefing?: Briefing
}

// 对话相关
export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

// 数据源相关
export interface DataSource {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  status: 'active' | 'inactive' | 'error'
  createdAt: string
  updatedAt: string
}

export interface DataSourceType {
  key: string
  label: string
  fields: DataSourceField[]
}

export interface DataSourceField {
  name: string
  label: string
  type: 'text' | 'password' | 'select' | 'number'
  required: boolean
  options?: { label: string; value: string }[]
}

// 模型相关
export interface ModelFolder {
  name: string
  path: string
  children?: ModelFolder[]
}

export interface ModelItem {
  name: string
  path: string
  size: number
  type: string
}

export interface ModelListResponse {
  folders: ModelFolder[]
  models: ModelItem[]
}

// 设置相关
export interface AppSettings {
  theme?: string
  language?: string
  [key: string]: unknown
}

export interface NotificationPreferences {
  email: boolean
  push: boolean
  [key: string]: unknown
}

export interface SettingsResponse {
  settings: AppSettings
}

export interface NotificationResponse {
  notifications: NotificationPreferences
}

// 优先级事项
export interface PriorityItem {
  id: string
  title: string
  priority: '高' | '中' | '低'
  status: 'pending' | 'completed'
  dueDate?: string
}

// 环境配置
export interface EnvConfig {
  name: string
  description: string
  color: string
  icon: string
  apiBaseUrl: string
  mockMode: boolean
}

// Graph 节点相关
export interface GraphNode {
  id: string
  type: string
  label: string
  status?: string
  data?: Record<string, unknown>
  upstream?: string[]
  downstream?: string[]
  retryCount?: number
  input?: unknown
  output?: unknown
  config?: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
}

export interface GraphState {
  nodes: GraphNode[]
  edges: GraphEdge[]
  results: Record<string, unknown>
  executionHistory: ExecutionRecord[]
  isRunning: boolean
}

export interface ExecutionRecord {
  nodeId: string
  timestamp: string
  status: 'success' | 'error'
  input?: unknown
  output?: unknown
  error?: string
}

// 任务相关
export interface Task {
  id: string
  name: string
  description: string
}

// 策略配置
export interface Strategy {
  tone: 'professional' | 'friendly' | 'persuasive'
  market: 'global' | 'us' | 'eu' | 'asia'
  seoStrength: 'low' | 'medium' | 'high'
  creativity: 'conservative' | 'balanced' | 'creative'
}

// 队列相关
export interface QueueConfig {
  maxConcurrent: number
  retryAttempts: number
  retryDelay: number
  timeout: number
  enablePriority: boolean
}

export interface QueueStatus {
  pending: number
  running: number
  completed: number
  failed: number
  isProcessing: boolean
  stats: {
    totalProcessed: number
    totalFailed: number
    totalRetries: number
    averageTime: number
  }
}

// 依赖解析相关
export interface DependencyInfo {
  upstream: string[]
  downstream: string[]
}

export interface BlockingStatus {
  isBlocked: boolean
  reason: string | null
  blockingNodes: string[]
}

export interface ExecutionProgress {
  total: number
  completed: number
  pending: number
  blocked: number
  progress: number
}

export interface ValidationResult {
  isValid: boolean
  errors: string[]
  warnings: string[]
}

// 节点状态
export interface NodeStateInfo {
  status: string
  lastUpdated: string
  previousStatus: string
}

// 结果渲染相关
export interface ResultSchema {
  id: string
  type: 'text' | 'markdown' | 'table' | 'chart' | 'image' | 'composite' | 'json'
  content: Record<string, unknown>
  editable: boolean
  meta: {
    sourceNode: string
    sourceType: string
    timestamp: number
    [key: string]: unknown
  }
}

// 事件相关
export interface EventPayload {
  [key: string]: unknown
  timestamp?: number
  source?: string
}

export type EventHandler = (payload: EventPayload) => void

// WebSocket 相关
export interface WSMessage {
  type: string
  data: unknown
  [key: string]: unknown
}
