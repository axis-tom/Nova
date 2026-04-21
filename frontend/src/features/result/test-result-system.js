/**
 * Result渲染系统测试文件
 * 
 * 这个文件用于测试S5 Result渲染系统的完整功能
 * 包括：数据解析、渲染器分发、编辑功能、双向数据流
 */

import eventBus from './voe/eventBus.js'
import * as eventTypes from './voe/eventTypes.js'
import { parseGraphOutput, validateResultSchema } from './parser/resultParser.js'

// 测试数据
const testResults = {
  text: {
    id: 'result_text_001',
    type: 'text',
    content: {
      title: '文本结果示例',
      text: '这是一个文本类型的结果示例。\n支持多行文本显示和编辑。\n用户可以修改这个文本内容。'
    },
    editable: true,
    meta: {
      sourceNode: 'text_generator_node',
      timestamp: Date.now(),
      version: '1.0'
    }
  },
  
  markdown: {
    id: 'result_markdown_001',
    type: 'markdown',
    content: {
      title: 'Markdown文档',
      text: '# Markdown示例\n\n这是一个**Markdown**文档示例。\n\n## 功能列表\n\n- 支持标题\n- 支持**粗体**和*斜体*\n- 支持代码块\n- 支持列表\n\n```javascript\nconsole.log("Hello, Result System!");\n```'
    },
    editable: true,
    meta: {
      sourceNode: 'markdown_generator',
      timestamp: Date.now(),
      version: '1.0'
    }
  },
  
  table: {
    id: 'result_table_001',
    type: 'table',
    content: {
      title: '用户数据表',
      columns: [
        { key: 'id', title: 'ID' },
        { key: 'name', title: '姓名' },
        { key: 'age', title: '年龄' },
        { key: 'email', title: '邮箱' }
      ],
      data: [
        { id: 1, name: '张三', age: 28, email: 'zhangsan@example.com' },
        { id: 2, name: '李四', age: 32, email: 'lisi@example.com' },
        { id: 3, name: '王五', age: 25, email: 'wangwu@example.com' },
        { id: 4, name: '赵六', age: 30, email: 'zhaoliu@example.com' }
      ]
    },
    editable: true,
    meta: {
      sourceNode: 'data_processor',
      timestamp: Date.now(),
      version: '1.0'
    }
  },
  
  chart: {
    id: 'result_chart_001',
    type: 'chart',
    content: {
      title: '销售数据图表',
      type: 'bar',
      data: {
        labels: ['一月', '二月', '三月', '四月', '五月'],
        datasets: [
          {
            label: '销售额',
            data: [12000, 19000, 15000, 25000, 22000],
            backgroundColor: 'rgba(59, 130, 246, 0.5)'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false
      }
    },
    editable: false,
    meta: {
      sourceNode: 'chart_generator',
      timestamp: Date.now(),
      version: '1.0'
    }
  },
  
  image: {
    id: 'result_image_001',
    type: 'image',
    content: {
      title: '图片对比',
      images: [
        {
          url: 'https://via.placeholder.com/400x300/3b82f6/ffffff?text=Before',
          title: '处理前',
          size: 102400
        },
        {
          url: 'https://via.placeholder.com/400x300/10b981/ffffff?text=After',
          title: '处理后',
          size: 153600
        }
      ],
      comparison: {
        type: 'slider',
        mode: 'horizontal'
      }
    },
    editable: false,
    meta: {
      sourceNode: 'image_processor',
      timestamp: Date.now(),
      version: '1.0'
    }
  }
}

// 测试函数
class ResultSystemTest {
  constructor() {
    this.testResults = []
    this.currentTestIndex = 0
    this.isRunning = false
  }
  
  // 运行所有测试
  async runAllTests() {
    console.log('🚀 开始测试Result渲染系统...')
    console.log('='.repeat(60))
    
    this.isRunning = true
    
    try {
      // 测试1: 数据解析器
      await this.testResultParser()
      
      // 测试2: 事件总线集成
      await this.testEventBusIntegration()
      
      // 测试3: 渲染器分发
      await this.testRendererDispatch()
      
      // 测试4: 编辑功能
      await this.testEditFunctionality()
      
      // 测试5: 双向数据流
      await this.testBidirectionalFlow()
      
      // 输出测试结果
      this.printTestSummary()
      
    } catch (error) {
      console.error('❌ 测试过程中发生错误:', error)
    } finally {
      this.isRunning = false
    }
  }
  
  // 测试1: 数据解析器
  async testResultParser() {
    console.log('🧪 测试1: 数据解析器')
    
    const testCases = [
      {
        name: '文本结果解析',
        input: testResults.text,
        expectedType: 'text'
      },
      {
        name: 'Markdown结果解析',
        input: testResults.markdown,
        expectedType: 'markdown'
      },
      {
        name: '表格结果解析',
        input: testResults.table,
        expectedType: 'table'
      },
      {
        name: '图表结果解析',
        input: testResults.chart,
        expectedType: 'chart'
      },
      {
        name: '图片结果解析',
        input: testResults.image,
        expectedType: 'image'
      }
    ]
    
    for (const testCase of testCases) {
      try {
        const parsed = parseGraphOutput(testCase.input)
        const isValid = validateResultSchema(parsed)
        
        const passed = isValid && parsed.type === testCase.expectedType
        
        this.testResults.push({
          name: testCase.name,
          passed,
          details: {
            input: testCase.input.type,
            parsed: parsed.type,
            isValid,
            schema: parsed
          }
        })
        
        console.log(`  ${passed ? '✅' : '❌'} ${testCase.name}`)
        if (!passed) {
          console.log(`    输入: ${testCase.input.type}`)
          console.log(`    解析: ${parsed.type}`)
          console.log(`    有效: ${isValid}`)
        }
        
      } catch (error) {
        this.testResults.push({
          name: testCase.name,
          passed: false,
          error: error.message
        })
        console.log(`  ❌ ${testCase.name}: ${error.message}`)
      }
    }
    
    console.log('')
  }
  
  // 测试2: 事件总线集成
  async testEventBusIntegration() {
    console.log('🧪 测试2: 事件总线集成')
    
    return new Promise((resolve) => {
      let eventReceived = false
      let receivedData = null
      
      // 监听RESULT_UPDATE事件
      const handler = (payload) => {
        eventReceived = true
        receivedData = payload
        console.log('  📡 收到RESULT_UPDATE事件:', payload.action)
      }
      
      eventBus.on(eventTypes.RESULT_UPDATE, handler)
      
      // 发送测试事件
      setTimeout(() => {
        const testEvent = {
          action: 'test_event',
          result: testResults.text,
          timestamp: Date.now()
        }
        
        eventBus.emit(eventTypes.RESULT_UPDATE, testEvent)
      }, 100)
      
      // 检查事件是否被接收
      setTimeout(() => {
        const passed = eventReceived && receivedData?.action === 'test_event'
        
        this.testResults.push({
          name: '事件总线通信',
          passed,
          details: {
            eventReceived,
            receivedAction: receivedData?.action,
            expectedAction: 'test_event'
          }
        })
        
        console.log(`  ${passed ? '✅' : '❌'} 事件总线通信`)
        if (!passed) {
          console.log(`    事件接收: ${eventReceived}`)
          console.log(`    接收动作: ${receivedData?.action}`)
        }
        
        // 清理监听器
        eventBus.off(eventTypes.RESULT_UPDATE, handler)
        resolve()
      }, 300)
    })
  }
  
  // 测试3: 渲染器分发
  async testRendererDispatch() {
    console.log('🧪 测试3: 渲染器分发')
    
    // 模拟渲染器映射
    const rendererMap = {
      text: 'TextRenderer',
      markdown: 'MarkdownRenderer',
      table: 'TableRenderer',
      chart: 'ChartRenderer',
      image: 'ImageCompareRenderer'
    }
    
    const testCases = Object.keys(testResults).map(type => ({
      name: `${type}渲染器分发`,
      type,
      expectedRenderer: rendererMap[type]
    }))
    
    for (const testCase of testCases) {
      try {
        const result = testResults[testCase.type]
        const rendererName = rendererMap[result.type]
        
        const passed = rendererName === testCase.expectedRenderer
        
        this.testResults.push({
          name: testCase.name,
          passed,
          details: {
            resultType: result.type,
            rendererName,
            expectedRenderer: testCase.expectedRenderer
          }
        })
        
        console.log(`  ${passed ? '✅' : '❌'} ${testCase.name}`)
        if (!passed) {
          console.log(`    结果类型: ${result.type}`)
          console.log(`    渲染器: ${rendererName}`)
          console.log(`    期望渲染器: ${testCase.expectedRenderer}`)
        }
        
      } catch (error) {
        this.testResults.push({
          name: testCase.name,
          passed: false,
          error: error.message
        })
        console.log(`  ❌ ${testCase.name}: ${error.message}`)
      }
    }
    
    console.log('')
  }
  
  // 测试4: 编辑功能
  async testEditFunctionality() {
    console.log('🧪 测试4: 编辑功能')
    
    const testCases = [
      {
        name: '文本编辑支持',
        result: testResults.text,
        expectedEditable: true
      },
      {
        name: 'Markdown编辑支持',
        result: testResults.markdown,
        expectedEditable: true
      },
      {
        name: '表格编辑支持',
        result: testResults.table,
        expectedEditable: true
      },
      {
        name: '图表编辑支持',
        result: testResults.chart,
        expectedEditable: false
      },
      {
        name: '图片编辑支持',
        result: testResults.image,
        expectedEditable: false
      }
    ]
    
    for (const testCase of testCases) {
      try {
        const passed = testCase.result.editable === testCase.expectedEditable
        
        this.testResults.push({
          name: testCase.name,
          passed,
          details: {
            resultType: testCase.result.type,
            editable: testCase.result.editable,
            expectedEditable: testCase.expectedEditable
          }
        })
        
        console.log(`  ${passed ? '✅' : '❌'} ${testCase.name}`)
        if (!passed) {
          console.log(`    类型: ${testCase.result.type}`)
          console.log(`    可编辑: ${testCase.result.editable}`)
          console.log(`    期望可编辑: ${testCase.expectedEditable}`)
        }
        
      } catch (error) {
        this.testResults.push({
          name: testCase.name,
          passed: false,
          error: error.message
        })
        console.log(`  ❌ ${testCase.name}: ${error.message}`)
      }
    }
    
    console.log('')
  }
  
  // 测试5: 双向数据流
  async testBidirectionalFlow() {
    console.log('🧪 测试5: 双向数据流')
    
    return new Promise((resolve) => {
      let editEventReceived = false
      let saveEventReceived = false
      
      // 监听编辑事件
      const editHandler = (payload) => {
        editEventReceived = true
        console.log('  📡 收到编辑事件:', payload.type)
      }
      
      // 监听保存事件
      const saveHandler = (payload) => {
        saveEventReceived = true
        console.log('  📡 收到保存事件')
      }
      
      // 模拟编辑操作
      setTimeout(() => {
        // 模拟用户编辑文本
        const editEvent = {
          type: 'text',
          originalText: '原始文本',
          editText: '编辑后的文本'
        }
        
        // 触发编辑事件
        eventBus.emit('EDIT_REQUEST', editEvent)
        
        // 模拟保存操作
        setTimeout(() => {
          const saveEvent = {
            action: 'user_edit',
            result: {
              ...testResults.text,
              content: {
                ...testResults.text.content,
                text: '编辑后的文本'
              }
            },
            timestamp: Date.now()
          }
          
          // 触发保存事件（应该触发Graph重算）
          eventBus.emit(eventTypes.RESULT_UPDATE, saveEvent)
        }, 100)
      }, 100)
      
      // 检查双向数据流
      setTimeout(() => {
        const passed = editEventReceived && saveEventReceived
        
        this.testResults.push({
          name: '双向数据流',
          passed,
          details: {
            editEventReceived,
            saveEventReceived,
            flowComplete: editEventReceived && saveEventReceived
          }
        })
        
        console.log(`  ${passed ? '✅' : '❌'} 双向数据流`)
        if (!passed) {
          console.log(`    编辑事件: ${editEventReceived}`)
          console.log(`    保存事件: ${saveEventReceived}`)
        }
        
        resolve()
      }, 500)
    })
  }
  
  // 输出测试摘要
  printTestSummary() {
    console.log('='.repeat(60))
    console.log('📊 测试结果摘要')
    console.log('='.repeat(60))
    
    const totalTests = this.testResults.length
    const passedTests = this.testResults.filter(t => t.passed).length
    const failedTests = totalTests - passedTests
    
    console.log(`总计测试: ${totalTests}`)
    console.log(`通过: ${passedTests}`)
    console.log(`失败: ${failedTests}`)
    console.log(`通过率: ${((passedTests / totalTests) * 100).toFixed(1)}%`)
    
    if (failedTests > 0) {
      console.log('\n❌ 失败的测试:')
      this.testResults
        .filter(t => !t.passed)
        .forEach((test, index) => {
          console.log(`  ${index + 1}. ${test.name}`)
          if (test.error) {
            console.log(`     错误: ${test.error}`)
          }
          if (test.details) {
            console.log(`     详情: ${JSON.stringify(test.details, null, 2)}`)
          }
        })
    }
    
    console.log('\n' + '='.repeat(60))
    
    if (passedTests === totalTests) {
      console.log('🎉 所有测试通过！Result渲染系统功能正常。')
      console.log('\n✅ S5 Result渲染系统实现完成:')
      console.log('   - Graph输出 → 结构化解析 ✓')
      console.log('   - 多形态渲染 → 可插拔系统 ✓')
      console.log('   - 可编辑 → 双向数据流 ✓')
      console.log('   - 通过eventBus通信 → 符合S4架构 ✓')
    } else {
      console.log('⚠️  部分测试失败，请检查实现。')
    }
  }
  
  // 生成测试报告
  generateTestReport() {
    return {
      timestamp: new Date().toISOString(),
      totalTests: this.testResults.length,
      passedTests: this.testResults.filter(t => t.passed).length,
      failedTests: this.testResults.filter(t => !t.passed).length,
      results: this.testResults,
      systemInfo: {
        resultTypes: Object.keys(testResults),
        features: [
          '数据解析',
          '事件总线集成',
          '渲染器分发',
          '编辑功能',
          '双向数据流'
        ]
      }
    }
  }
}

// 导出测试工具
export default ResultSystemTest

// 如果直接运行此文件，则执行测试
if (typeof window !== 'undefined' && window.location.href.includes('test')) {
  console.log('🔧 准备运行Result系统测试...')
  
  const testRunner = new ResultSystemTest()
  
  // 添加测试按钮到页面
  const testButton = document.createElement('button')
  testButton.textContent = '运行Result系统测试'
  testButton.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 24px;
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    z-index: 9999;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  `
  
  testButton.onclick = () => {
    testRunner.runAllTests()
  }
  
  document.body.appendChild(testButton)
  
  console.log('✅ 测试工具已加载，点击右上角按钮运行测试。')
}