/**
 * VOE系统集成示例
 * 
 * 展示如何将VOE事件交互层集成到现有组件中
 */

import { initializeVOESystem, uiBridge, eventBus } from './index.js'

/**
 * 示例1: 集成到Vue组件中
 * 
 * 假设有一个Vue组件需要与VOE系统交互
 */
export function createVueComponentIntegration() {
  return {
    data() {
      return {
        voeInitialized: false,
        selectedNode: null,
        executionStatus: 'idle'
      }
    },
    
    async mounted() {
      // 初始化VOE系统
      try {
        await initializeVOESystem()
        this.voeInitialized = true
        console.log('VOE系统已集成到Vue组件')
        
        // 监听相关事件
        this.setupEventListeners()
      } catch (error) {
        console.error('VOE系统初始化失败:', error)
      }
    },
    
    methods: {
      /**
       * 设置事件监听器
       */
      setupEventListeners() {
        // 监听节点选择事件
        eventBus.on('NODE_SELECT', (payload) => {
          this.selectedNode = payload.nodeId
          console.log('Vue组件: 节点已选择', payload)
        })
        
        // 监听节点状态变化
        eventBus.on('NODE_STATUS_CHANGE', (payload) => {
          if (payload.nodeId === this.selectedNode) {
            this.executionStatus = payload.status
            console.log('Vue组件: 节点状态变化', payload)
          }
        })
        
        // 监听结果更新
        eventBus.on('RESULT_UPDATE', (payload) => {
          console.log('Vue组件: 结果已更新', payload)
          // 这里可以更新组件的数据或触发重新渲染
        })
      },
      
      /**
       * 处理节点点击（从Vue组件调用）
       */
      handleNodeClick(node) {
        if (!this.voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        
        // 通过UI Bridge处理节点点击
        uiBridge.handleClickNode(node)
      },
      
      /**
       * 处理任务提交（从Vue组件调用）
       */
      handleTaskSubmit(taskData) {
        if (!this.voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        
        // 通过UI Bridge处理任务提交
        uiBridge.handleTaskSubmit(taskData)
      },
      
      /**
       * 处理结果编辑（从Vue组件调用）
       */
      handleResultEdit(resultData) {
        if (!this.voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        
        // 通过UI Bridge处理结果编辑
        uiBridge.handleResultEdit(resultData)
      }
    },
    
    beforeUnmount() {
      // 清理事件监听器（如果需要）
      // 注意：eventBus.on返回的取消函数可以用于清理
    }
  }
}

/**
 * 示例2: 集成到React组件中
 * 
 * 假设有一个React组件需要与VOE系统交互
 */
export function createReactComponentIntegration() {
  // 这是一个React Hooks示例
  return function useVOEIntegration() {
    const [voeInitialized, setVoeInitialized] = React.useState(false)
    const [selectedNode, setSelectedNode] = React.useState(null)
    const [executionStatus, setExecutionStatus] = React.useState('idle')
    
    // 初始化VOE系统
    React.useEffect(() => {
      let isMounted = true
      
      const initVOE = async () => {
        try {
          await initializeVOESystem()
          if (isMounted) {
            setVoeInitialized(true)
            console.log('VOE系统已集成到React组件')
          }
        } catch (error) {
          console.error('VOE系统初始化失败:', error)
        }
      }
      
      initVOE()
      
      return () => {
        isMounted = false
      }
    }, [])
    
    // 设置事件监听器
    React.useEffect(() => {
      if (!voeInitialized) return
      
      const unsubscribeNodeSelect = eventBus.on('NODE_SELECT', (payload) => {
        setSelectedNode(payload.nodeId)
        console.log('React组件: 节点已选择', payload)
      })
      
      const unsubscribeNodeStatus = eventBus.on('NODE_STATUS_CHANGE', (payload) => {
        if (payload.nodeId === selectedNode) {
          setExecutionStatus(payload.status)
          console.log('React组件: 节点状态变化', payload)
        }
      })
      
      const unsubscribeResultUpdate = eventBus.on('RESULT_UPDATE', (payload) => {
        console.log('React组件: 结果已更新', payload)
        // 这里可以触发状态更新或副作用
      })
      
      return () => {
        unsubscribeNodeSelect()
        unsubscribeNodeStatus()
        unsubscribeResultUpdate()
      }
    }, [voeInitialized, selectedNode])
    
    // 返回可用的方法和状态
    return {
      voeInitialized,
      selectedNode,
      executionStatus,
      
      // 方法
      handleNodeClick: (node) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.handleClickNode(node)
      },
      
      handleTaskSubmit: (taskData) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.handleTaskSubmit(taskData)
      },
      
      handleResultEdit: (resultData) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.handleResultEdit(resultData)
      },
      
      triggerNodeRun: (nodeId, parameters) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.triggerNodeRun({ nodeId, parameters })
      }
    }
  }
}

/**
 * 示例3: 集成到普通JavaScript模块中
 */
export function integrateWithExistingModule(existingModule) {
  // 初始化VOE系统
  let voeInitialized = false
  
  const init = async () => {
    try {
      await initializeVOESystem()
      voeInitialized = true
      console.log('VOE系统已集成到现有模块:', existingModule.name || '未知模块')
      
      // 扩展现有模块的功能
      extendModuleFunctionality()
      
    } catch (error) {
      console.error('VOE系统集成失败:', error)
    }
  }
  
  const extendModuleFunctionality = () => {
    // 添加VOE相关方法到现有模块
    existingModule.voe = {
      // 状态
      isInitialized: () => voeInitialized,
      
      // 方法
      handleNodeClick: (node) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.handleClickNode(node)
      },
      
      handleTaskSubmit: (taskData) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.handleTaskSubmit(taskData)
      },
      
      triggerNodeRun: (nodeId, parameters) => {
        if (!voeInitialized) {
          console.warn('VOE系统未初始化')
          return
        }
        uiBridge.triggerNodeRun({ nodeId, parameters })
      },
      
      // 事件监听
      onNodeSelect: (callback) => {
        return eventBus.on('NODE_SELECT', callback)
      },
      
      onResultUpdate: (callback) => {
        return eventBus.on('RESULT_UPDATE', callback)
      },
      
      onGraphProgress: (callback) => {
        return eventBus.on('GRAPH_PROGRESS', callback)
      }
    }
    
    // 如果现有模块有相关方法，可以重写或扩展它们
    if (existingModule.handleNodeClick) {
      const originalHandleNodeClick = existingModule.handleNodeClick
      existingModule.handleNodeClick = function(node) {
        // 调用原始方法
        originalHandleNodeClick.call(this, node)
        // 同时通过VOE系统处理
        uiBridge.handleClickNode(node)
      }
    }
  }
  
  // 返回初始化函数
  return {
    init,
    getStatus: () => ({ voeInitialized })
  }
}

/**
 * 示例4: 创建VOE系统包装器
 * 
 * 为现有应用提供统一的VOE接口
 */
export function createVOEWrapper(appContext) {
  const wrapper = {
    // 状态
    initialized: false,
    
    // 初始化
    async initialize() {
      if (this.initialized) return
      
      try {
        await initializeVOESystem()
        this.initialized = true
        
        // 设置应用特定的事件监听
        this.setupAppSpecificListeners()
        
        console.log('VOE包装器已初始化，应用上下文:', appContext)
        
      } catch (error) {
        console.error('VOE包装器初始化失败:', error)
        throw error
      }
    },
    
    // 设置应用特定的事件监听
    setupAppSpecificListeners() {
      // 监听所有UI操作事件
      eventBus.on('UI_ACTION', (payload) => {
        console.log('应用UI操作:', payload)
        // 这里可以添加应用特定的处理逻辑
      })
      
      // 监听Graph执行事件
      eventBus.on('GRAPH_START', () => {
        console.log('应用: Graph开始执行')
        // 更新应用状态
      })
      
      eventBus.on('GRAPH_FINISH', (payload) => {
        console.log('应用: Graph执行完成', payload)
        // 处理最终结果
      })
    },
    
    // 应用方法
    methods: {
      // 节点相关
      selectNode: (node) => {
        if (!wrapper.initialized) {
          console.warn('VOE包装器未初始化')
          return
        }
        uiBridge.handleClickNode(node)
      },
      
      runNode: (nodeId, parameters) => {
        if (!wrapper.initialized) {
          console.warn('VOE包装器未初始化')
          return
        }
        uiBridge.triggerNodeRun({ nodeId, parameters })
      },
      
      // 任务相关
      submitTask: (taskData) => {
        if (!wrapper.initialized) {
          console.warn('VOE包装器未初始化')
          return
        }
        uiBridge.handleTaskSubmit(taskData)
      },
      
      // 结果相关
      editResult: (resultData) => {
        if (!wrapper.initialized) {
          console.warn('VOE包装器未初始化')
          return
        }
        uiBridge.handleResultEdit(resultData)
      },
      
      // 事件监听
      on: (eventType, callback) => {
        return eventBus.on(eventType, callback)
      },
      
      off: (eventType) => {
        // 注意：实际实现需要根据eventBus的具体API调整
        // 这里假设eventBus有off方法
        if (eventBus.off) {
          eventBus.off(eventType)
        }
      }
    },
    
    // 获取状态
    getStatus() {
      return {
        initialized: this.initialized,
        appContext
      }
    }
  }
  
  return wrapper
}

/**
 * 使用示例
 */
export function demonstrateIntegration() {
  console.log('=== VOE系统集成示例 ===\n')
  
  // 示例1: 创建Vue组件集成
  console.log('1. Vue组件集成示例:')
  const vueIntegration = createVueComponentIntegration()
  console.log('Vue集成对象已创建:', vueIntegration)
  
  // 示例2: 创建React Hook集成
  console.log('\n2. React Hook集成示例:')
  const reactIntegration = createReactComponentIntegration()
  console.log('React Hook已创建:', reactIntegration)
  
  // 示例3: 集成到现有模块
  console.log('\n3. 现有模块集成示例:')
  const existingModule = {
    name: '数据分析模块',
    handleNodeClick: function(node) {
      console.log('原始模块处理节点点击:', node)
    }
  }
  
  const moduleIntegration = integrateWithExistingModule(existingModule)
  console.log('模块集成已设置:', moduleIntegration)
  
  // 示例4: 创建VOE包装器
  console.log('\n4. VOE包装器示例:')
  const appContext = { appName: 'Nova Workspace', version: '1.0.0' }
  const voeWrapper = createVOEWrapper(appContext)
  console.log('VOE包装器已创建:', voeWrapper.getStatus())
  
  console.log('\n=== 集成示例演示完成 ===')
  
  return {
    vueIntegration,
    reactIntegration,
    moduleIntegration,
    voeWrapper
  }
}

// 导出所有集成示例
export default {
  createVueComponentIntegration,
  createReactComponentIntegration,
  integrateWithExistingModule,
  createVOEWrapper,
  demonstrateIntegration
}