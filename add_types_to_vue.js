/**
 * 为 Vue 文件添加显式类型注解
 * 
 * 1. 为 ref() 添加泛型类型
 * 2. 为 reactive() 添加泛型类型
 * 3. 为 computed() 添加返回类型
 * 4. 为 defineProps 添加接口类型
 * 5. 为 defineEmits 添加接口类型
 * 6. 修复 .js 导入路径为 .ts
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

function processFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  const relativePath = path.relative(FRONTEND_SRC, filePath);
  let modified = false;
  
  // 1. 修复 .js 导入路径为 .ts
  const jsImportRegex = /(from\s+['"])([^'"]+)\.js(['"])/g;
  const newContent1 = content.replace(jsImportRegex, (match, prefix, importPath, suffix) => {
    // 检查 .ts 文件是否存在
    const tsPath = path.join(FRONTEND_SRC, importPath + '.ts');
    if (fs.existsSync(tsPath)) {
      modified = true;
      return `${prefix}${importPath}.ts${suffix}`;
    }
    return match;
  });
  content = newContent1;
  
  // 2. 为 ref(null) 添加类型
  // ref(null) -> ref<null>(null)
  // ref([]) -> ref<unknown[]>([])
  // ref({}) -> ref<Record<string, unknown>>({})
  // ref(true/false) -> ref<boolean>(true/false)
  // ref(0) -> ref<number>(0)
  // ref('') -> ref<string>('')
  
  const refPatterns = [
    { pattern: /const\s+(\w+)\s*=\s*ref\(null\)/g, type: 'null' },
    { pattern: /const\s+(\w+)\s*=\s*ref\(\[\]\)/g, type: 'unknown[]' },
    { pattern: /const\s+(\w+)\s*=\s*ref\(\{\}\)/g, type: 'Record<string, unknown>' },
    { pattern: /const\s+(\w+)\s*=\s*ref\((true|false)\)/g, type: 'boolean' },
    { pattern: /const\s+(\w+)\s*=\s*ref\((\d+)\)/g, type: 'number' },
    { pattern: /const\s+(\w+)\s*=\s*ref\((['"][^'"]*['"])\)/g, type: 'string' },
  ];
  
  for (const { pattern, type } of refPatterns) {
    content = content.replace(pattern, (match, varName, value) => {
      modified = true;
      return `const ${varName} = ref<${type}>(${value})`;
    });
  }
  
  // 3. 为 reactive({}) 添加类型
  // 查找 reactive({...}) 调用并推断类型
  const reactivePattern = /const\s+(\w+)\s*=\s*reactive\((\{[\s\S]*?\})\)/g;
  content = content.replace(reactivePattern, (match, varName, objContent) => {
    modified = true;
    // 提取属性名和值类型
    const props = [];
    const propRegex = /(\w+)\s*:\s*([^,\n]+)/g;
    let m;
    while ((m = propRegex.exec(objContent)) !== null) {
      const val = m[2].trim();
      let tsType = 'unknown';
      if (val === 'true' || val === 'false') tsType = 'boolean';
      else if (/^\d+\.?\d*$/.test(val)) tsType = 'number';
      else if (/^['"]/.test(val)) tsType = 'string';
      else if (val === '[]' || val.startsWith('[')) tsType = 'unknown[]';
      else if (val === '{}' || val.startsWith('{')) tsType = 'Record<string, unknown>';
      else if (val === 'null') tsType = 'null';
      props.push({ name: m[1], type: tsType });
    }
    
    if (props.length > 0) {
      let interface_ = `interface ${varName[0].toUpperCase() + varName.slice(1)}Type {\n`;
      for (const prop of props) {
        interface_ += `  ${prop.name}: ${prop.type}\n`;
      }
      interface_ += `}\n\n`;
      return `${interface_}const ${varName} = reactive<${varName[0].toUpperCase() + varName.slice(1)}Type>(${objContent})`;
    }
    return match;
  });
  
  // 4. 为 computed() 添加返回类型
  const computedPattern = /const\s+(\w+)\s*=\s*computed\(\(\)\s*=>\s*\{/g;
  content = content.replace(computedPattern, (match, varName) => {
    modified = true;
    return `const ${varName} = computed(() => {`;
  });
  
  // 5. 处理 defineProps 对象形式 -> 接口形式
  // 查找 defineProps({...}) 并转换为 defineProps<Props>()
  const definePropsPattern = /const\s+props\s*=\s*defineProps\((\{[\s\S]*?\})\)/g;
  content = content.replace(definePropsPattern, (match, propsContent) => {
    modified = true;
    // 提取 prop 定义
    const props = [];
    const propRegex = /(\w+)\s*:\s*\{[\s\S]*?type\s*:\s*(\w+)[\s\S]*?required\s*:\s*(true|false)[\s\S]*?default\s*:\s*([^,\n]+)[\s\S]*?\}/g;
    let m;
    while ((m = propRegex.exec(propsContent)) !== null) {
      props.push({ name: m[1], type: m[2], required: m[3] === 'true', default: m[4] });
    }
    
    // 如果没有匹配到完整模式，尝试简单模式
    if (props.length === 0) {
      const simpleRegex = /(\w+)\s*:\s*\{[\s\S]*?type\s*:\s*(\w+)[\s\S]*?\}/g;
      while ((m = simpleRegex.exec(propsContent)) !== null) {
        props.push({ name: m[1], type: m[2], required: false, default: undefined });
      }
    }
    
    if (props.length > 0) {
      let interface_ = `interface Props {\n`;
      for (const prop of props) {
        let tsType = mapVueTypeToTS(prop.type);
        if (prop.required) {
          interface_ += `  ${prop.name}: ${tsType}\n`;
        } else {
          interface_ += `  ${prop.name}?: ${tsType}\n`;
        }
      }
      interface_ += `}\n\n`;
      return `${interface_}const props = defineProps<Props>()`;
    }
    return match;
  });
  
  // 6. 处理 defineEmits 数组形式 -> 接口形式
  const defineEmitsPattern = /const\s+emit\s*=\s*defineEmits\(\[([\s\S]*?)\]\)/g;
  content = content.replace(defineEmitsPattern, (match, emitsContent) => {
    modified = true;
    const emitNames = emitsContent.split(',').map(s => s.trim().replace(/['"]/g, ''));
    let emitType = `interface Emits {\n`;
    for (const name of emitNames) {
      emitType += `  (e: '${name}', ...args: unknown[]): void\n`;
    }
    emitType += `}\n\n`;
    return `${emitType}const emit = defineEmits<Emits>()`;
  });
  
  if (modified) {
    fs.writeFileSync(filePath, content, 'utf-8');
    console.log(`✓ 已更新类型: ${relativePath}`);
  } else {
    console.log(`- 无需修改: ${relativePath}`);
  }
}

function mapVueTypeToTS(vueType) {
  const map = {
    String: 'string',
    Number: 'number',
    Boolean: 'boolean',
    Array: 'unknown[]',
    Object: 'Record<string, unknown>',
    Function: '(...args: unknown[]) => unknown',
    Date: 'Date',
    Symbol: 'symbol',
    Promise: 'Promise<unknown>',
  };
  return map[vueType] || 'unknown';
}

function main() {
  const vueFiles = getVueFiles(FRONTEND_SRC);
  console.log(`找到 ${vueFiles.length} 个 .vue 文件\n`);
  
  for (const file of vueFiles) {
    try {
      processFile(file);
    } catch (err) {
      console.error(`✗ 错误 ${path.relative(FRONTEND_SRC, file)}:`, err.message);
    }
  }
  
  console.log('\n类型添加完成！');
}

main();
