/**
 * 修复 ref<null>(NNNN) 为 ref<Type | null>(null)
 * 根据变量名推断合适的类型
 */
const fs = require('fs');
const path = require('path');

const FRONTEND_SRC = '/home/nova/nova/frontend/src';

function getVueFiles(dir) {
  const files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...getVueFiles(fullPath));
    } else if (entry.name.endsWith('.vue')) {
      files.push(fullPath);
    }
  }
  return files;
}

function inferType(varName) {
  const name = varName.toLowerCase();
  if (name.includes('ref') || name.includes('input') || name.includes('textarea') || 
      name.includes('scrollbar') || name.includes('canvas') || name.includes('editor') ||
      name.includes('container') || name.includes('form') || name.includes('avatar') ||
      name.includes('element') || name.includes('node')) {
    return 'HTMLElement';
  }
  if (name.includes('result') || name.includes('data') || name.includes('trace') || 
      name.includes('info') || name.includes('detail') || name.includes('schema') ||
      name.includes('briefing') || name.includes('project') || name.includes('conversation')) {
    return 'unknown';
  }
  if (name.includes('id') || name.includes('key') || name.includes('index')) {
    return 'string';
  }
  if (name.includes('error') || name.includes('status') || name.includes('timeout')) {
    return 'unknown';
  }
  if (name.includes('format') || name.includes('type')) {
    return 'string';
  }
  return 'unknown';
}

function processFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  const relativePath = path.relative(FRONTEND_SRC, filePath);
  
  // 修复 ref<null>(NNNN) -> ref<Type | null>(null)
  const pattern = /const\s+(\w+)\s*=\s*ref<null>\(\d+\)/g;
  let match;
  let modified = false;
  
  while ((match = pattern.exec(content)) !== null) {
    const varName = match[1];
    const tsType = inferType(varName);
    const replacement = `const ${varName} = ref<${tsType} | null>(null)`;
    content = content.replace(match[0], replacement);
    modified = true;
    console.log(`  ${varName}: ref<null>(NNNN) -> ref<${tsType} | null>(null)`);
  }
  
  if (modified) {
    fs.writeFileSync(filePath, content, 'utf-8');
    console.log(`✓ 已修复: ${relativePath}`);
  }
}

function main() {
  const vueFiles = getVueFiles(FRONTEND_SRC);
  console.log(`检查 ${vueFiles.length} 个 .vue 文件中的 ref<null> 问题\n`);
  
  for (const file of vueFiles) {
    processFile(file);
  }
  
  console.log('\n修复完成！');
}

main();
