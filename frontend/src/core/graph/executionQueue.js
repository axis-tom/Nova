/**
 * 执行队列
 * 
 * 职责：控制执行顺序，防止并发冲突
 * 
 * 规则：
 * - FIFO（先进先出）
 * - 同一节点不重复执行
 */

/**
 * 队列配置
 */
const QUEUE_CONFIG = {
  maxConcurrent: 1, // 最大并发数
  retryAttempts: 3, // 重试次数
  retryDelay: 1000, // 重试延迟（毫秒）
  timeout: 30000, // 超时时间（毫秒）
  enablePriority: false // 是否启用优先级
}

/**
 * 队列状态
 */
let queueState = {
  items: [],
  running: new Set(),
  completed: new Map(),
  failed: new Map(),
  isProcessing: false,
  stats: {
    totalProcessed: 0,
    totalFailed: 0,
    totalRetries: 0,
    averageTime: 0
  }
}

/**
 * 队列项
 */
class QueueItem {
  constructor(id, task, priority = 0, metadata = {}) {
    this.id = id
    this.task = task
    this.priority = priority
    this.metadata = metadata
    this.status = 'pending'
    this.createdAt = Date.now()
    this.startedAt = null
    this.completedAt = null
    this.retryCount = 0
    this.error = null
    this.result = null
  }
}

/**
 * 添加任务到队列
 * @param {Function} task - 要执行的任务函数
 * @param {Object} options - 选项
 * @returns {Promise} 执行结果
 */
export async function enqueue(task, options = {}) {
  const taskId = options.id || generateTaskId()
  const priority = options.priority || 0
  const metadata = options.metadata || {}
  
  // 检查是否已经在队列中
  if (isInQueue(taskId)) {
    console.warn(`任务 ${taskId} 已在队列中，跳过重复添加`)
    return Promise.reject(new Error('任务已在队列中'))
  }
  
  // 检查是否已经完成
  if (queueState.completed.has(taskId)) {
    console.log(`任务 ${taskId} 已完成，返回缓存结果`)
    return Promise.resolve(queueState.completed.get(taskId))
  }
  
  // 创建队列项
  const queueItem = new QueueItem(taskId, task, priority, metadata)
  
  // 添加到队列
  if (QUEUE_CONFIG.enablePriority) {
    // 按优先级插入
    insertByPriority(queueItem)
  } else {
    // FIFO
    queueState.items.push(queueItem)
  }
  
  console.log(`任务 ${taskId} 已加入队列，当前队列长度: ${queueState.items.length}`)
  
  // 开始处理队列
  if (!queueState.isProcessing) {
    processQueue()
  }
  
  // 返回Promise，等待任务完成
  return new Promise((resolve, reject) => {
    const checkInterval = setInterval(() => {
      // 先检查是否已完成
      if (queueState.completed.has(taskId)) {
        clearInterval(checkInterval);
        resolve(queueState.completed.get(taskId));
        return;
      }
      
      // 再检查是否失败
      if (queueState.failed.has(taskId)) {
        clearInterval(checkInterval);
        reject(queueState.failed.get(taskId));
        return;
      }
      
      // 最后检查队列项是否存在（可能已被清理）
      const item = getQueueItem(taskId);
      if (!item) {
        // 任务可能已经完成但尚未加入 completed 映射（竞态条件）
        // 再等一会儿，如果还是找不到就报错
        setTimeout(() => {
          if (queueState.completed.has(taskId)) {
            resolve(queueState.completed.get(taskId));
          } else if (queueState.failed.has(taskId)) {
            reject(queueState.failed.get(taskId));
          } else {
            clearInterval(checkInterval);
            reject(new Error('任务状态未知'));
          }
        }, 50);
        return;
      }
      
      // 正常状态检查
      if (item.status === 'completed') {
        clearInterval(checkInterval);
        resolve(item.result);
      } else if (item.status === 'failed') {
        clearInterval(checkInterval);
        reject(item.error);
      }
    }, 100);
  });
}

/**
 * 批量添加任务
 * @param {Array} tasks - 任务数组
 * @param {Object} options - 选项
 * @returns {Promise} 所有任务结果
 */
export async function batchEnqueue(tasks, options = {}) {
  console.log(`批量添加 ${tasks.length} 个任务到队列`)
  
  const promises = tasks.map((task, index) => {
    const taskOptions = {
      id: options.ids ? options.ids[index] : generateTaskId(),
      priority: options.priorities ? options.priorities[index] : 0,
      metadata: options.metadata ? options.metadata[index] : {}
    }
    
    return enqueue(task, taskOptions)
      .then(result => ({ success: true, result }))
      .catch(error => ({ success: false, error }))
  })
  
  const results = await Promise.all(promises)
  
  const summary = {
    total: results.length,
    success: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length
  }
  
  console.log(`批量任务完成: ${summary.success} 成功, ${summary.failed} 失败`)
  return results
}

/**
 * 处理队列
 */
async function processQueue() {
  if (queueState.isProcessing) {
    return
  }
  
  queueState.isProcessing = true
  console.log('开始处理队列')
  
  while (queueState.items.length > 0 && queueState.running.size < QUEUE_CONFIG.maxConcurrent) {
    // 获取下一个任务
    const queueItem = getNextQueueItem()
    if (!queueItem) {
      break
    }
    
    // 从队列中移除
    removeFromQueue(queueItem.id)
    
    // 添加到运行中集合
    queueState.running.add(queueItem.id)
    
    // 执行任务
    executeTask(queueItem)
      .finally(() => {
        // 从运行中集合移除
        queueState.running.delete(queueItem.id)
        
        // 更新统计
        updateStats(queueItem)
        
        // 继续处理队列
        if (queueState.items.length > 0) {
          processQueue()
        } else if (queueState.running.size === 0) {
          // 队列为空且没有运行中的任务
          queueState.isProcessing = false
          console.log('队列处理完成')
        }
      })
  }
  
  if (queueState.items.length === 0 && queueState.running.size === 0) {
    queueState.isProcessing = false
  }
}

/**
 * 执行任务
 * @param {QueueItem} queueItem - 队列项
 */
async function executeTask(queueItem) {
  console.log(`开始执行任务: ${queueItem.id}`)
  
  queueItem.status = 'running'
  queueItem.startedAt = Date.now()
  
  try {
    // 设置超时
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('任务执行超时')), QUEUE_CONFIG.timeout)
    })
    
    // 执行任务
    const taskPromise = queueItem.task()
    const result = await Promise.race([taskPromise, timeoutPromise])
    
    // 任务成功
    queueItem.status = 'completed'
    queueItem.completedAt = Date.now()
    queueItem.result = result
    
    // 添加到已完成映射
    queueState.completed.set(queueItem.id, result)
    
    console.log(`任务 ${queueItem.id} 执行成功，耗时: ${queueItem.completedAt - queueItem.startedAt}ms`)
    
  } catch (error) {
    // 任务失败
    queueItem.status = 'failed'
    queueItem.completedAt = Date.now()
    queueItem.error = error
    
    // 添加到失败映射
    queueState.failed.set(queueItem.id, error)
    
    console.error(`任务 ${queueItem.id} 执行失败:`, error)
    
    // 检查是否需要重试
    if (queueItem.retryCount < QUEUE_CONFIG.retryAttempts) {
      queueItem.retryCount++
      console.log(`任务 ${queueItem.id} 准备重试 (${queueItem.retryCount}/${QUEUE_CONFIG.retryAttempts})`)
      
      // 延迟后重新加入队列
      setTimeout(() => {
        queueItem.status = 'pending'
        queueItem.error = null
        
        if (QUEUE_CONFIG.enablePriority) {
          insertByPriority(queueItem)
        } else {
          queueState.items.push(queueItem)
        }
        
        queueState.stats.totalRetries++
        
        // 继续处理队列
        if (!queueState.isProcessing) {
          processQueue()
        }
      }, QUEUE_CONFIG.retryDelay)
    }
  }
}

/**
 * 获取下一个队列项
 * @returns {QueueItem} 队列项
 */
function getNextQueueItem() {
  if (queueState.items.length === 0) {
    return null
  }
  
  if (QUEUE_CONFIG.enablePriority) {
    // 按优先级获取（优先级数字越大，优先级越高）
    return queueState.items.reduce((highest, current) => {
      return current.priority > highest.priority ? current : highest
    }, queueState.items[0])
  } else {
    // FIFO
    return queueState.items[0]
  }
}

/**
 * 按优先级插入队列项
 * @param {QueueItem} queueItem - 队列项
 */
function insertByPriority(queueItem) {
  let inserted = false
  
  for (let i = 0; i < queueState.items.length; i++) {
    if (queueItem.priority > queueState.items[i].priority) {
      queueState.items.splice(i, 0, queueItem)
      inserted = true
      break
    }
  }
  
  if (!inserted) {
    queueState.items.push(queueItem)
  }
}

/**
 * 检查任务是否在队列中
 * @param {string} taskId - 任务ID
 * @returns {boolean} 是否在队列中
 */
function isInQueue(taskId) {
  return queueState.items.some(item => item.id === taskId) ||
         queueState.running.has(taskId)
}

/**
 * 获取队列项
 * @param {string} taskId - 任务ID
 * @returns {QueueItem} 队列项
 */
function getQueueItem(taskId) {
  // 在队列中查找
  const inQueue = queueState.items.find(item => item.id === taskId)
  if (inQueue) {
    return inQueue
  }
  
  // 在运行中查找
  if (queueState.running.has(taskId)) {
    // 这里需要维护一个运行中任务的映射
    // 简化实现：返回一个占位符
    return {
      id: taskId,
      status: 'running'
    }
  }
  
  return null
}

/**
 * 从队列中移除
 * @param {string} taskId - 任务ID
 */
function removeFromQueue(taskId) {
  const index = queueState.items.findIndex(item => item.id === taskId)
  if (index !== -1) {
    queueState.items.splice(index, 1)
  }
}

/**
 * 更新统计信息
 * @param {QueueItem} queueItem - 队列项
 */
function updateStats(queueItem) {
  if (queueItem.status === 'completed') {
    queueState.stats.totalProcessed++
    
    // 更新平均时间
    const executionTime = queueItem.completedAt - queueItem.startedAt
    if (queueState.stats.averageTime === 0) {
      queueState.stats.averageTime = executionTime
    } else {
      queueState.stats.averageTime = 
        (queueState.stats.averageTime * (queueState.stats.totalProcessed - 1) + executionTime) / 
        queueState.stats.totalProcessed
    }
  } else if (queueItem.status === 'failed' && queueItem.retryCount >= QUEUE_CONFIG.retryAttempts) {
    queueState.stats.totalFailed++
  }
}

/**
 * 生成任务ID
 * @returns {string} 任务ID
 */
function generateTaskId() {
  return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

/**
 * 获取队列状态
 * @returns {Object} 队列状态
 */
export function getQueueStatus() {
  return {
    pending: queueState.items.length,
    running: queueState.running.size,
    completed: queueState.completed.size,
    failed: queueState.failed.size,
    isProcessing: queueState.isProcessing,
    stats: { ...queueState.stats }
  }
}

/**
 * 获取队列项详情
 * @param {string} taskId - 任务ID
 * @returns {Object} 队列项详情
 */
export function getQueueItemDetails(taskId) {
  const item = getQueueItem(taskId)
  if (!item) {
    return null
  }
  
  return {
    id: item.id,
    status: item.status,
    priority: item.priority,
    metadata: item.metadata,
    createdAt: item.createdAt,
    startedAt: item.startedAt,
    completedAt: item.completedAt,
    retryCount: item.retryCount,
    error: item.error,
    result: item.result
  }
}

/**
 * 获取所有队列项
 * @returns {Array} 所有队列项
 */
export function getAllQueueItems() {
  const items = []
  
  // 添加待处理项
  queueState.items.forEach(item => {
    items.push({
      id: item.id,
      status: 'pending',
      priority: item.priority,
      metadata: item.metadata,
      createdAt: item.createdAt
    })
  })
  
  // 添加运行中项
  queueState.running.forEach(taskId => {
    items.push({
      id: taskId,
      status: 'running'
    })
  })
  
  // 添加已完成项
  queueState.completed.forEach((result, taskId) => {
    // 需要从原始队列项获取更多信息
    // 简化实现
    items.push({
      id: taskId,
      status: 'completed',
      result: result
    })
  })
  
  // 添加失败项
  queueState.failed.forEach((error, taskId) => {
    items.push({
      id: taskId,
      status: 'failed',
      error: error.message
    })
  })
  
  return items
}

/**
 * 清空队列
 */
export function clearQueue() {
  queueState.items = []
  queueState.running.clear()
  queueState.completed.clear()
  queueState.failed.clear()
  queueState.isProcessing = false
  
  console.log('队列已清空')
}

/**
 * 暂停队列处理
 */
export function pauseQueue() {
  queueState.isProcessing = false
  console.log('队列处理已暂停')
}

/**
 * 恢复队列处理
 */
export function resumeQueue() {
  if (!queueState.isProcessing && queueState.items.length > 0) {
    processQueue()
    console.log('队列处理已恢复')
  }
}

/**
 * 移除特定任务
 * @param {string} taskId - 任务ID
 * @returns {boolean} 是否成功移除
 */
export function removeTask(taskId) {
  // 从待处理队列中移除
  const pendingIndex = queueState.items.findIndex(item => item.id === taskId)
  if (pendingIndex !== -1) {
    queueState.items.splice(pendingIndex, 1)
    console.log(`任务 ${taskId} 已从待处理队列中移除`)
    return true
  }
  
  // 无法移除运行中的任务
  if (queueState.running.has(taskId)) {
    console.warn(`任务 ${taskId} 正在运行中，无法移除`)
    return false
  }
  
  // 从已完成映射中移除
  if (queueState.completed.has(taskId)) {
    queueState.completed.delete(taskId)
    console.log(`任务 ${taskId} 已从已完成映射中移除`)
    return true
  }
  
  // 从失败映射中移除
  if (queueState.failed.has(taskId)) {
    queueState.failed.delete(taskId)
    console.log(`任务 ${taskId} 已从失败映射中移除`)
    return true
  }
  
  console.warn(`任务 ${taskId} 不存在`)
  return false
}

/**
 * 更新队列配置
 * @param {Object} newConfig - 新配置
 */
export function updateQueueConfig(newConfig) {
  Object.assign(QUEUE_CONFIG, newConfig)
  console.log('队列配置已更新:', QUEUE_CONFIG)
}

/**
 * 获取队列配置
 * @returns {Object} 队列配置
 */
export function getQueueConfig() {
  return { ...QUEUE_CONFIG }
}