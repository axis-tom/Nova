/**
 * VOE系统测试文件
 * 
 * 测试VOE事件交互层的基本功能
 */

import { initializeVOESystem, getVOEStatus, eventBus } from './index.js'

/**
 * 运行VOE系统测试
 */
async function runVOETests() {
  console.log('🚀 开始VOE系统测试...\n')
  
  try {
    // 1. 初始化VOE系统
    console.log('1. 初始化VOE系统...')
    const voeSystem = await initializeVOESystem()
    console.log('✅ VOE系统初始化成功\n')
    
    // 2. 检查系统状态
    console.log('2. 检查系统状态...')
    const status = getVOEStatus()
    console.log('系统状态:', JSON.stringify(status, null, 2))
    console.log('✅ 系统状态检查完成\n')
    
    // 3. 测试事件总线
    console.log('3. 测试事件总线...')
    let testEventReceived = false
    const unsubscribe = eventBus.on('TEST_EVENT', (payload) => {
      console.log('✅ 收到测试事件:', payload)
      testEventReceived = true
    })
    
    eventBus.emit('TEST_EVENT', { message: 'Hello VOE!', timestamp: Date.now() })
    
    // 等待事件处理
    await new Promise(resolve => setTimeout(resolve, 100))
    
    if (testEventReceived) {
      console.log('✅ 事件总线测试通过\n')
    } else {
      console.log('❌ 事件总线测试失败\n')
    }
    
    unsubscribe()
    
    // 4. 测试UI Bridge功能
    console.log('4. 测试UI Bridge功能...')
    console.log('模拟节点点击...')
    
    // 监听节点选择事件
    let nodeSelectReceived = false
    const unsubscribeNodeSelect = eventBus.on('NODE_SELECT', (payload) => {
      console.log('✅ 收到节点选择事件:', payload)
      nodeSelectReceived = true
    })
    
    // 触发节点点击
    voeSystem.triggerNodeClick({
      id: 'test-node-1',
      type: 'analysis',
      label: '测试节点'
    })
    
    // 等待事件处理
    await new Promise(resolve => setTimeout(resolve, 100))
    
    if (nodeSelectReceived) {
      console.log('✅ UI Bridge测试通过\n')
    } else {
      console.log('❌ UI Bridge测试失败\n')
    }
    
    unsubscribeNodeSelect()
    
    // 5. 测试节点运行
    console.log('5. 测试节点运行...')
    console.log('模拟节点运行...')
    
    // 监听节点运行事件
    let nodeRunReceived = false
    const unsubscribeNodeRun = eventBus.on('NODE_RUN', (payload) => {
      console.log('✅ 收到节点运行事件:', payload)
      nodeRunReceived = true
    })
    
    // 触发节点运行
    voeSystem.triggerNodeRun('test-node-1', { param1: 'value1' })
    
    // 等待事件处理
    await new Promise(resolve => setTimeout(resolve, 100))
    
    if (nodeRunReceived) {
      console.log('✅ 节点运行测试通过\n')
    } else {
      console.log('❌ 节点运行测试失败\n')
    }
    
    unsubscribeNodeRun()
    
    // 6. 测试Graph开始
    console.log('6. 测试Graph开始...')
    console.log('模拟Graph开始...')
    
    // 监听Graph开始事件
    let graphStartReceived = false
    const unsubscribeGraphStart = eventBus.on('GRAPH_START', (payload) => {
      console.log('✅ 收到Graph开始事件:', payload)
      graphStartReceived = true
    })
    
    // 触发Graph开始
    voeSystem.triggerGraphStart()
    
    // 等待事件处理
    await new Promise(resolve => setTimeout(resolve, 100))
    
    if (graphStartReceived) {
      console.log('✅ Graph开始测试通过\n')
    } else {
      console.log('❌ Graph开始测试失败\n')
    }
    
    unsubscribeGraphStart()
    
    // 7. 测试事件流完整性
    console.log('7. 测试事件流完整性...')
    console.log('模拟完整事件流: UI点击 → 节点选择 → 节点运行 → Graph开始')
    
    const eventFlow = []
    const eventTypesToTrack = ['UI_ACTION', 'NODE_SELECT', 'NODE_RUN', 'GRAPH_START']
    
    const trackers = eventTypesToTrack.map(eventType => {
      return eventBus.on(eventType, (payload) => {
        eventFlow.push({
          eventType,
          timestamp: Date.now(),
          payload: { ...payload, source: payload.source || 'unknown' }
        })
        console.log(`📝 事件流记录: ${eventType}`)
      })
    })
    
    // 触发完整事件流
    voeSystem.triggerNodeClick({
      id: 'test-node-2',
      type: 'generation',
      label: '生成节点'
    })
    
    // 等待事件处理
    await new Promise(resolve => setTimeout(resolve, 200))
    
    console.log('\n事件流记录:')
    eventFlow.forEach((event, index) => {
      console.log(`${index + 1}. ${event.eventType} - ${new Date(event.timestamp).toISOString()}`)
    })
    
    if (eventFlow.length >= 2) {
      console.log('✅ 事件流完整性测试通过\n')
    } else {
      console.log('❌ 事件流完整性测试失败\n')
    }
    
    // 清理跟踪器
    trackers.forEach(unsubscribe => unsubscribe())
    
    // 8. 测试结果
    console.log('8. 测试结果总结...')
    const allTests = [
      { name: '系统初始化', passed: voeSystem.isInitialized },
      { name: '事件总线', passed: testEventReceived },
      { name: 'UI Bridge', passed: nodeSelectReceived },
      { name: '节点运行', passed: nodeRunReceived },
      { name: 'Graph开始', passed: graphStartReceived },
      { name: '事件流完整性', passed: eventFlow.length >= 2 }
    ]
    
    const passedTests = allTests.filter(test => test.passed).length
    const totalTests = allTests.length
    
    console.log('\n📊 测试结果汇总:')
    allTests.forEach(test => {
      console.log(`${test.passed ? '✅' : '❌'} ${test.name}`)
    })
    
    console.log(`\n🎯 测试完成: ${passedTests}/${totalTests} 通过`)
    
    if (passedTests === totalTests) {
      console.log('🎉 所有测试通过！VOE系统功能正常。')
    } else {
      console.log('⚠️  部分测试失败，请检查系统配置。')
    }
    
  } catch (error) {
    console.error('❌ 测试过程中发生错误:', error)
    console.error(error.stack)
  }
}

/**
 * 运行简单的手动测试
 */
async function runSimpleTest() {
  console.log('🧪 运行简单VOE测试...')
  
  try {
    // 初始化系统
    await initializeVOESystem()
    console.log('✅ 系统初始化完成')
    
    // 测试事件发射和接收
    const testMessage = 'VOE系统测试消息'
    let receivedMessage = null
    
    eventBus.on('SIMPLE_TEST', (payload) => {
      receivedMessage = payload.message
      console.log(`✅ 收到事件: ${receivedMessage}`)
    })
    
    eventBus.emit('SIMPLE_TEST', { message: testMessage })
    
    // 等待事件处理
    await new Promise(resolve => setTimeout(resolve, 50))
    
    if (receivedMessage === testMessage) {
      console.log('✅ 简单测试通过')
    } else {
      console.log('❌ 简单测试失败')
    }
    
  } catch (error) {
    console.error('测试错误:', error)
  }
}

// 根据参数决定运行哪种测试
const testType = process.argv[2] || 'simple'

if (testType === 'full') {
  runVOETests()
} else {
  runSimpleTest()
}

export { runVOETests, runSimpleTest }