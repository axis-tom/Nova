/**
 * Mock数据源API
 * 用于UI-7任务：展示数据源列表（mock数据），不调用真实后端
 */

// Mock数据源列表
const mockDataSources = [
  {
    id: 1,
    name: '公司邮箱',
    type: 'email',
    enabled: true,
    lastSync: '2024-01-15T10:30:00Z',
    config: {
      provider: 'qq',
      email: 'company@example.com',
      password: '********',
      imapHost: 'imap.qq.com',
      imapPort: 993
    }
  },
  {
    id: 2,
    name: '行业新闻RSS',
    type: 'rss',
    enabled: true,
    lastSync: '2024-01-14T14:20:00Z',
    config: {
      url: 'https://example.com/industry-news/rss',
      interval: 3600,
      categories: ['科技', '金融']
    }
  },
  {
    id: 3,
    name: '微博监控',
    type: 'weibo',
    enabled: false,
    lastSync: '2024-01-10T09:15:00Z',
    config: {
      keywords: ['人工智能', '机器学习'],
      accounts: ['technews', 'ai_research'],
      interval: 1800
    }
  },
  {
    id: 4,
    name: '小红书品牌监测',
    type: 'xiaohongshu',
    enabled: true,
    lastSync: '2024-01-15T08:45:00Z',
    config: {
      brand: 'NovaAI',
      keywords: ['智能助手', 'AI工具'],
      interval: 7200
    }
  },
  {
    id: 5,
    name: '财务数据源',
    type: 'financial',
    enabled: true,
    lastSync: '2024-01-15T16:30:00Z',
    config: {
      apiKey: '********',
      endpoints: ['stock', 'forex', 'crypto'],
      updateFrequency: 'realtime'
    }
  }
];

// Mock数据源类型定义
const mockDataSourceTypes = {
  email: {
    name: '邮箱',
    fields: [
      { name: 'provider', label: '邮箱提供商', type: 'select', required: true, 
        options: [
          { value: 'qq', label: 'QQ邮箱' },
          { value: 'gmail', label: 'Gmail' },
          { value: '163', label: '163邮箱' },
          { value: 'outlook', label: 'Outlook' }
        ]
      },
      { name: 'email', label: '邮箱地址', type: 'text', required: true, placeholder: '请输入邮箱地址' },
      { name: 'password', label: '密码/授权码', type: 'password', required: true }
    ]
  },
  rss: {
    name: 'RSS订阅',
    fields: [
      { name: 'url', label: 'RSS地址', type: 'text', required: true, placeholder: '请输入RSS地址' },
      { name: 'interval', label: '更新间隔(秒)', type: 'number', required: true, placeholder: '3600' },
      { name: 'categories', label: '分类标签', type: 'text', placeholder: '用逗号分隔，如：科技,金融' }
    ]
  },
  weibo: {
    name: '微博',
    fields: [
      { name: 'keywords', label: '关键词', type: 'text', required: true, placeholder: '用逗号分隔，如：人工智能,机器学习' },
      { name: 'accounts', label: '监控账号', type: 'text', placeholder: '用逗号分隔，如：technews,ai_research' },
      { name: 'interval', label: '更新间隔(秒)', type: 'number', required: true, placeholder: '1800' }
    ]
  },
  xiaohongshu: {
    name: '小红书',
    fields: [
      { name: 'brand', label: '品牌名称', type: 'text', required: true, placeholder: '请输入品牌名称' },
      { name: 'keywords', label: '关键词', type: 'text', required: true, placeholder: '用逗号分隔，如：智能助手,AI工具' },
      { name: 'interval', label: '更新间隔(秒)', type: 'number', required: true, placeholder: '7200' }
    ]
  },
  financial: {
    name: '金融数据',
    fields: [
      { name: 'apiKey', label: 'API密钥', type: 'password', required: true },
      { name: 'endpoints', label: '数据端点', type: 'text', placeholder: '用逗号分隔，如：stock,forex,crypto' },
      { name: 'updateFrequency', label: '更新频率', type: 'select', required: true,
        options: [
          { value: 'realtime', label: '实时' },
          { value: 'hourly', label: '每小时' },
          { value: 'daily', label: '每日' }
        ]
      }
    ]
  }
};

// 模拟延迟
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * 获取所有数据源（mock）
 */
export async function getDataSources() {
  console.log('[Mock API] 获取数据源列表');
  await delay(300);
  return mockDataSources;
}

/**
 * 获取单个数据源详情（mock）
 */
export async function getDataSource(id) {
  console.log(`[Mock API] 获取数据源详情 ID: ${id}`);
  await delay(200);
  const source = mockDataSources.find(s => s.id === parseInt(id));
  if (!source) {
    throw new Error(`数据源 ${id} 不存在`);
  }
  return source;
}

/**
 * 创建数据源（mock）
 */
export async function createDataSource(data) {
  console.log('[Mock API] 创建数据源:', data);
  await delay(400);
  
  const newId = Math.max(...mockDataSources.map(s => s.id)) + 1;
  const newSource = {
    id: newId,
    ...data,
    enabled: true,
    lastSync: null,
    config: data.config || {}
  };
  
  // 模拟添加到列表（实际不会修改mock数据）
  console.log('[Mock API] 数据源创建成功（模拟）:', newSource);
  
  return {
    ...newSource,
    message: '数据源创建成功（模拟）'
  };
}

/**
 * 更新数据源（mock）
 */
export async function updateDataSource(id, data) {
  console.log(`[Mock API] 更新数据源 ID: ${id}`, data);
  await delay(300);
  
  const sourceIndex = mockDataSources.findIndex(s => s.id === parseInt(id));
  if (sourceIndex === -1) {
    throw new Error(`数据源 ${id} 不存在`);
  }
  
  const updatedSource = {
    ...mockDataSources[sourceIndex],
    ...data,
    id: parseInt(id)
  };
  
  console.log('[Mock API] 数据源更新成功（模拟）:', updatedSource);
  
  return {
    ...updatedSource,
    message: '数据源更新成功（模拟）'
  };
}

/**
 * 删除数据源（mock）
 */
export async function deleteDataSource(id) {
  console.log(`[Mock API] 删除数据源 ID: ${id}`);
  await delay(250);
  
  const sourceIndex = mockDataSources.findIndex(s => s.id === parseInt(id));
  if (sourceIndex === -1) {
    throw new Error(`数据源 ${id} 不存在`);
  }
  
  console.log(`[Mock API] 数据源 ${id} 删除成功（模拟）`);
  
  return {
    success: true,
    message: '数据源删除成功（模拟）'
  };
}

/**
 * 测试数据源连接（mock）
 */
export async function testDataSource(config) {
  console.log('[Mock API] 测试数据源连接:', config);
  await delay(500);
  
  // 模拟测试结果
  const success = Math.random() > 0.3; // 70%成功率
  
  if (success) {
    return {
      success: true,
      message: '连接测试成功（模拟）'
    };
  } else {
    return {
      success: false,
      message: '连接测试失败：模拟错误（模拟）'
    };
  }
}

/**
 * 获取数据源类型（mock）
 */
export async function getDataSourceTypes() {
  console.log('[Mock API] 获取数据源类型');
  await delay(200);
  return mockDataSourceTypes;
}

/**
 * 使用环境参数的mock API包装器
 */
export function createMockDataSourceApi(envStore) {
  return {
    getDataSources: (params = {}) => {
      console.log(`[Mock API with Env] 获取数据源列表，环境: ${envStore.currentEnv}`);
      return getDataSources();
    },
    getDataSource: (id, params = {}) => {
      console.log(`[Mock API with Env] 获取数据源详情 ID: ${id}，环境: ${envStore.currentEnv}`);
      return getDataSource(id);
    },
    createDataSource: (data, params = {}) => {
      console.log(`[Mock API with Env] 创建数据源，环境: ${envStore.currentEnv}`, data);
      return createDataSource(data);
    },
    updateDataSource: (id, data, params = {}) => {
      console.log(`[Mock API with Env] 更新数据源 ID: ${id}，环境: ${envStore.currentEnv}`, data);
      return updateDataSource(id, data);
    },
    deleteDataSource: (id, params = {}) => {
      console.log(`[Mock API with Env] 删除数据源 ID: ${id}，环境: ${envStore.currentEnv}`);
      return deleteDataSource(id);
    },
    testDataSource: (config, params = {}) => {
      console.log(`[Mock API with Env] 测试数据源连接，环境: ${envStore.currentEnv}`, config);
      return testDataSource(config);
    },
    getDataSourceTypes: (params = {}) => {
      console.log(`[Mock API with Env] 获取数据源类型，环境: ${envStore.currentEnv}`);
      return getDataSourceTypes();
    }
  };
}