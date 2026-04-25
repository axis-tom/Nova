// Type declarations for .js modules that haven't been converted to TypeScript yet

declare module '@/utils/websocket' {
  interface WsManager {
    connect(url: string, token?: string): void
    disconnect(): void
    send(data: Record<string, unknown>): void
    on(event: string, handler: (data: Record<string, unknown>) => void): void
    off(event: string, handler: (data: Record<string, unknown>) => void): void
  }
  export const wsManager: WsManager
}

declare module '@/utils/format' {
  export function formatDate(date: string | Date | number, format?: string): string
  export function timeAgo(date: string | Date | number): string
  export function formatTime(date: string | Date): string
  export function formatDuration(seconds: number): string
  export function formatNumber(num: number): string
  export function truncate(str: string, length: number): string
  export function formatFileSize(bytes: number): string
  export function formatRelativeTime(date: string | Date | number): string
}

declare module '@/stores/dataSources' {
  import { defineStore } from 'pinia'
  export const useDataSourceStore: ReturnType<typeof defineStore>
}

declare module '@/stores/environment' {
  import { defineStore } from 'pinia'
  export const useEnvironmentStore: ReturnType<typeof defineStore>
}

declare module '@/api/graph' {
  export function getGraphSchema(scenario: string): Promise<Record<string, unknown>>
  export function listScenarios(): Promise<Record<string, unknown>>
  export function runGraph(data: Record<string, unknown>): Promise<Record<string, unknown>>
  export function getTraceDebugInfo(traceId: string): Promise<Record<string, unknown>>
  export function replayTrace(traceId: string, options?: Record<string, unknown>): Promise<Record<string, unknown>>
  export function retryTrace(traceId: string): Promise<Record<string, unknown>>
  export function getTraceDetails(traceId: string): Promise<Record<string, unknown>>
}
