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
} from './graphEngine.js';

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
} from './nodeStateMachine.js';

// 导出 nodeRunner
export {
  execute,
  batchExecute,
  validateInput,
  getExecutionConfig,
  getSupportedNodeTypes,
  NODE_TYPE
} from './nodeRunner.js';

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
} from './dependencyResolver.js';

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
} from './executionQueue.js';

// 工具函数（保留原样）
export function createGraphExecutor(options = {}) {
  return {
    initialize: (nodes, edges) => {
      return import('./graphEngine.js').then(module => {
        module.initializeGraph(nodes, edges);
        return module;
      });
    },
    runNode: (nodeId) => {
      return import('./graphEngine.js').then(module => module.runNode(nodeId));
    },
    runFromNode: (nodeId) => {
      return import('./graphEngine.js').then(module => module.runFromNode(nodeId));
    },
    executeAll: () => {
      return import('./graphEngine.js').then(module => module.executeAll());
    },
    markDirtyChain: (nodeId) => {
      return import('./graphEngine.js').then(module => module.markDirtyChain(nodeId));
    },
    retryNode: (nodeId) => {
      return import('./graphEngine.js').then(module => module.retryNode(nodeId));
    },
    getGraphState: () => {
      return import('./graphEngine.js').then(module => module.getGraphState());
    },
    resetGraph: () => {
      return import('./graphEngine.js').then(module => module.resetGraph());
    }
  };
}

export function createGraphManager(options = {}) {
  const executor = createGraphExecutor(options);
  return {
    ...executor,
    getNodeStatus: (nodeId) => {
      return import('./nodeStateMachine.js').then(module => module.getStatus(nodeId));
    },
    setNodeStatus: (nodeId, status) => {
      return import('./nodeStateMachine.js').then(module => module.setStatus(nodeId, status));
    },
    canExecute: (nodeId, nodes) => {
      return import('./dependencyResolver.js').then(module => module.canExecute(nodeId, nodes));
    },
    getExecutionOrder: (nodes) => {
      return import('./dependencyResolver.js').then(module => module.getExecutionOrder(nodes));
    },
    getQueueStatus: () => {
      return import('./executionQueue.js').then(module => module.getQueueStatus());
    },
    clearQueue: () => {
      return import('./executionQueue.js').then(module => module.clearQueue());
    },
    batchExecuteNodes: (nodeIds) => {
      return Promise.all(nodeIds.map(nodeId => executor.runNode(nodeId)));
    },
    onNodeStatusChange: (callback) => {
      return import('./nodeStateMachine.js').then(module => {
        module.onStatusChange(callback);
        return () => module.offStatusChange(callback);
      });
    }
  };
}

let defaultGraphManager = null;

export function getDefaultGraphManager() {
  if (!defaultGraphManager) {
    defaultGraphManager = createGraphManager();
  }
  return defaultGraphManager;
}

export function setDefaultGraphManager(manager) {
  defaultGraphManager = manager;
}

export const GRAPH_ENGINE_VERSION = '1.0.0';
export const GRAPH_ENGINE_AUTHOR = 'Nova Team';
export const GRAPH_ENGINE_DESCRIPTION = 'Nova Graph执行引擎';