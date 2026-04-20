// 测试Console页面访问和旧系统兼容性
const fs = require('fs');
const path = require('path');

console.log('🔍 测试Nova前端Console重构兼容性\n');

// 1. 检查路由文件
console.log('1. 检查路由配置...');
const routerPath = path.join(__dirname, 'frontend/src/router/index.js');
const routerContent = fs.readFileSync(routerPath, 'utf8');

// 检查是否包含Console路由
const hasConsoleRoute = routerContent.includes("path: '/console'");
const hasConsoleImport = routerContent.includes("const Console = () => import('@/views/Console.vue')");

console.log(`   ✅ Console路由导入: ${hasConsoleImport ? '存在' : '缺失'}`);
console.log(`   ✅ Console路由定义: ${hasConsoleRoute ? '存在' : '缺失'}`);

// 检查旧路由是否仍然存在
const oldRoutes = [
  '/dashboard',
  '/data-sources',
  '/briefings',
  '/logs',
  '/settings',
  '/marketplace'
];

let oldRoutesCount = 0;
oldRoutes.forEach(route => {
  if (routerContent.includes(`path: '${route}'`)) {
    oldRoutesCount++;
  }
});

console.log(`   ✅ 旧路由保留: ${oldRoutesCount}/${oldRoutes.length} 个`);

// 2. 检查Console视图文件
console.log('\n2. 检查Console视图文件...');
const consoleViewPath = path.join(__dirname, 'frontend/src/views/Console.vue');
const consoleViewExists = fs.existsSync(consoleViewPath);
console.log(`   ✅ Console.vue文件: ${consoleViewExists ? '存在' : '缺失'}`);

if (consoleViewExists) {
  const consoleContent = fs.readFileSync(consoleViewPath, 'utf8');
  const hasConsoleLayout = consoleContent.includes('console-layout');
  const hasDarkTheme = consoleContent.includes('#0f172a') || consoleContent.includes('--console-bg-base');
  console.log(`   ✅ Console布局: ${hasConsoleLayout ? '存在' : '缺失'}`);
  console.log(`   ✅ 深色主题: ${hasDarkTheme ? '存在' : '缺失'}`);
}

// 3. 检查App.vue修改
console.log('\n3. 检查App.vue修改...');
const appVuePath = path.join(__dirname, 'frontend/src/App.vue');
const appVueContent = fs.readFileSync(appVuePath, 'utf8');
const hasConsoleExclusion = appVueContent.includes("route.name === 'Console'");
console.log(`   ✅ Console独立布局: ${hasConsoleExclusion ? '已配置' : '未配置'}`);

// 4. 检查Console组件
console.log('\n4. 检查Console组件...');
const consoleComponents = [
  'ConsolePanel.vue',
  'TraceList.vue',
  'DebugTools.vue'
];

consoleComponents.forEach(component => {
  const componentPath = path.join(__dirname, 'frontend/src/components/console', component);
  const exists = fs.existsSync(componentPath);
  console.log(`   ✅ ${component}: ${exists ? '存在' : '缺失'}`);
});

// 5. 检查主题文件
console.log('\n5. 检查主题文件...');
const themePath = path.join(__dirname, 'frontend/src/assets/css/console-theme.css');
const themeExists = fs.existsSync(themePath);
console.log(`   ✅ Console主题文件: ${themeExists ? '存在' : '缺失'}`);

// 总结
console.log('\n📊 测试总结:');
console.log('='.repeat(50));

const tests = [
  { name: 'Console路由导入', passed: hasConsoleImport },
  { name: 'Console路由定义', passed: hasConsoleRoute },
  { name: '旧路由保留', passed: oldRoutesCount === oldRoutes.length },
  { name: 'Console视图文件', passed: consoleViewExists },
  { name: 'Console独立布局', passed: hasConsoleExclusion },
  { name: 'Console组件创建', passed: consoleComponents.every(c => 
    fs.existsSync(path.join(__dirname, 'frontend/src/components/console', c))
  )},
  { name: 'Console主题文件', passed: themeExists }
];

let passedTests = 0;
tests.forEach(test => {
  const status = test.passed ? '✅' : '❌';
  console.log(`   ${status} ${test.name}`);
  if (test.passed) passedTests++;
});

console.log('='.repeat(50));
console.log(`\n🎯 通过率: ${passedTests}/${tests.length} (${Math.round(passedTests/tests.length * 100)}%)`);

if (passedTests === tests.length) {
  console.log('\n✨ 所有测试通过！Console重构完成，旧系统保持兼容。');
  console.log('\n🚀 使用说明:');
  console.log('   1. 启动前端: cd frontend && npm run dev');
  console.log('   2. 访问Console: http://localhost:5173/console');
  console.log('   3. 访问旧系统: http://localhost:5173/dashboard');
  console.log('\n📌 注意事项:');
  console.log('   - Console使用独立深色主题布局');
  console.log('   - 旧页面保持原有样式和功能');
  console.log('   - 所有新功能只写在Console内');
  console.log('   - 符合"边写边不乱"原则');
} else {
  console.log('\n⚠️  部分测试未通过，请检查上述问题。');
  process.exit(1);
}