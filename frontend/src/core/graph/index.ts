/**
 * Graph执行引擎 - 主入口文件
 */

// 显式导出 graphEngine 的所有非冲突函数
export {
  initializeGraph,
  runNode,
  runFromNode,
  executeAll,
  markDirtyChain,
  retryNode as graphRetryNode,  // 重命名避免冲突
  getNodeStatus as getGraphNodeStatus,
  getNodeResult,
  getGraphState,
  resetGraph
} from './graphEngine';

// 显式导出 nodeStateMachine 的函数
export {
  setStatus,
  getStatus,
  resetNode,
  markDirty,
  retryNode as stateMachineRetryNode,  // 重命名避免冲突
  getStatusHistory,
  canExecute as stateCanExecute,
  isDone,
  isRunning,
  isError,
  isDirty,
  batchSetStatus,
  batchResetNodes,
  getAllNodeStatuses,
  clearAllStatuses,
  onStatusChange,
  offStatusChange,
  getStateTransitionGraph,
  validateTransitionPath,
  NODE_STATE
} from './nodeStateMachine';

// 导出 nodeRunner
export {
  execute,
  batchExecute,
  validateInput,
  getExecutionConfig,
  getSupportedNodeTypes,
  NODE_TYPE
} from './nodeRunner';

// 导出 dependencyResolver
export {
  canExecute,
  getExecutionOrder,
  getDownstreamChain,
  getUpstreamChain,
  hasCyclicDependency,
  getDirectDependencies,
  getAllDependencies,
  getBlockingStatus,
  getExecutableNodes,
  getExecutionProgress,
  validateDependencies
} from './dependencyResolver';

// 导出 executionQueue
export {
  enqueue,
  batchEnqueue,
  getQueueStatus,
  getQueueItemDetails,
  getAllQueueItems,
  clearQueue,
  pauseQueue,
  resumeQueue,
  removeTask,
  updateQueueConfig,
  getQueueConfig
} from './executionQueue';

import type { GraphNode, GraphEdge } from '@/types';
import type { getGraphState as getGraphStateType } from './graphEngine';

// 工具函数（保留原样）
export function createGraphExecutor(options: Record<string, unknown> = {}): {
  initialize: (nodes: GraphNode[], edges: GraphEdge[]) => Promise<typeof import('./graphEngine')>;
  runNode: (nodeId: string) => Promise<unknown>;
  runFromNode: (nodeId: string) => Promise<Record<string, unknown>>;
  executeAll: () => Promise<Record<string, unknown>>;
  markDirtyChain: (nodeId: string) => Promise<void>;
  retryNode: (nodeId: string) => Promise<unknown>;
  getGraphState: () => Promise<ReturnType<typeof getGraphStateType>>;
  resetGraph: () => Promise<void>;
} {
  return {
    initialize: (nodes, edges) => {
      return import('./graphEngine').then(module => {
        module.initializeGraph(nodes, edges);
        return module;
      });
    },
    runNode: (nodeId) => {
      return import('./graphEngine').then(module => module.runNode(nodeId));
    },
    runFromNode: (nodeId) => {
      return import('./graphEngine').then(module => module.runFromNode(nodeId));
    },
    executeAll: () => {
      return import('./graphEngine').then(module => module.executeAll());
    },
    markDirtyChain: (nodeId) => {
      return import('./graphEngine').then(module => module.markDirtyChain(nodeId));
    },
    retryNode: (nodeId) => {
      return import('./graphEngine').then(module => module.retryNode(nodeId));
    },
    getGraphState: () => {
      return import('./graphEngine').then(module => module.getGraphState());
    },
    resetGraph: () => {
      return import('./graphEngine').then(module => module.resetGraph());
    }
  };
}

export function createGraphManager(options: Record<string, unknown> = {}): ReturnType<typeof createGraphExecutor> & {
  getNodeStatus: (nodeId: string) => Promise<string>;
  setNodeStatus: (nodeId: string, status: string) => Promise<void>;
  canExecute: (nodeId: string, nodes: GraphNode[]) => Promise<boolean>;
  getExecutionOrder: (nodes: GraphNode[]) => Promise<string[]>;
  getQueueStatus: () => Promise<ReturnType<typeof import('./executionQueue').getQueueStatus>>;
  clearQueue: () => Promise<void>;
  batchExecuteNodes: (nodeIds: string[]) => Promise<unknown[]>;
  onNodeStatusChange: (callback: (nodeId: string, oldStatus: string, newStatus: string) => void) => Promise<() => void>;
} {
  const executor = createGraphExecutor(options);
  return {
    ...executor,
    getNodeStatus: (nodeId) => {
      return import('./nodeStateMachine').then(module => module.getStatus(nodeId));
    },
    setNodeStatus: (nodeId, status) => {
      return import('./nodeStateMachine').then(module => module.setStatus(nodeId, status));
    },
    canExecute: (nodeId, nodes) => {
      return import('./dependencyResolver').then(module => module.canExecute(nodeId, nodes));
    },
    getExecutionOrder: (nodes) => {
      return import('./dependencyResolver').then(module => module.getExecutionOrder(nodes));
    },
    getQueueStatus: () => {
      return import('./executionQueue').then(module => module.getQueueStatus());
    },
    clearQueue: () => {
      return import('./executionQueue').then(module => module.clearQueue());
    },
    batchExecuteNodes: (nodeIds) => {
      return Promise.all(nodeIds.map(nodeId => executor.runNode(nodeId)));
    },
    onNodeStatusChange: (callback) => {
      return import('./nodeStateMachine').then(module => {
        module.onStatusChange(callback);
        return () => module.offStatusChange(callback);
      });
    }
  };
}

let defaultGraphManager: ReturnType<typeof createGraphManager> | null = null;

export function getDefaultGraphManager(): ReturnType<typeof createGraphManager> {
  if (!defaultGraphManager) {
    defaultGraphManager = createGraphManager();
  }
  return defaultGraphManager;
}

export function setDefaultGraphManager(manager: ReturnType<typeof createGraphManager>): void {
  defaultGraphManager = manager;
}

export const GRAPH_ENGINE_VERSION = '1.0.0';
export const GRAPH_ENGINE_AUTHOR = 'Nova Team';
export const GRAPH_ENGINE_DESCRIPTION = 'Nova Graph执行引擎';
