/**
 * Vue 文件 <script> 升级为 <script setup lang="ts"> 转换脚本
 * 
 * 处理所有 .vue 文件，将 <script> 块升级为 <script setup lang="ts">
 * 并添加显式类型定义
 */
const fs = require('fs');
const path = require('path');

const FRONTEND_SRC = '/home/nova/nova/frontend/src';

// 获取所有 .vue 文件
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

// 检查文件是否已有 <script setup>
function hasScriptSetup(content) {
  return /<script\s+setup/.test(content);
}

// 检查文件是否已有 lang="ts"
function hasLangTs(content) {
  return /<script[^>]*lang\s*=\s*["']ts["']/.test(content);
}

// 提取 script 块内容
function extractScriptBlock(content) {
  const match = content.match(/<script[^>]*>([\s\S]*?)<\/script>/);
  return match ? match[1].trim() : null;
}

// 替换 script 标签
function replaceScriptTag(content, newScriptContent, isSetup) {
  const setupAttr = isSetup ? ' setup' : '';
  const tsAttr = ' lang="ts"';
  const newTag = `<script${setupAttr}${tsAttr}>\n${newScriptContent}\n</script>`;
  return content.replace(/<script[^>]*>[\s\S]*?<\/script>/, newTag);
}

// 判断是否包含 defineProps
function hasDefineProps(content) {
  return /defineProps\s*\(/.test(content);
}

// 判断是否包含 defineEmits
function hasDefineEmits(content) {
  return /defineEmits\s*\(/.test(content);
}

// 判断是否包含 defineExpose
function hasDefineExpose(content) {
  return /defineExpose\s*\(/.test(content);
}

// 判断是否包含 emits 选项
function hasEmitsOption(content) {
  return /emits\s*:\s*\[/.test(content) || /emits\s*:\s*\{/.test(content);
}

// 提取 props 定义
function extractPropsDefinition(content) {
  const match = content.match(/props\s*:\s*\{([\s\S]*?)\}\s*[,\n]/);
  return match ? match[0] : null;
}

// 提取 emits 定义
function extractEmitsDefinition(content) {
  const match = content.match(/emits\s*:\s*\[([\s\S]*?)\]/);
  return match ? match[0] : null;
}

// 将 props 对象定义转换为 TypeScript 接口
function propsToInterface(propsContent, interfaceName) {
  // 简单实现：提取 prop 名称和类型
  const propNames = [];
  const propRegex = /(\w+)\s*:\s*\{[\s\S]*?type\s*:\s*(\w+)/g;
  let match;
  while ((match = propRegex.exec(propsContent)) !== null) {
    propNames.push({ name: match[1], type: match[2] });
  }
  
  let interface_ = `interface ${interfaceName} {\n`;
  for (const prop of propNames) {
    let tsType = mapVueTypeToTS(prop.type);
    interface_ += `  ${prop.name}?: ${tsType}\n`;
  }
  interface_ += `}`;
  return interface_;
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

// 处理单个文件
function processFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  const relativePath = path.relative(FRONTEND_SRC, filePath);
  
  // 如果已经有 <script setup lang="ts">，跳过
  if (hasScriptSetup(content) && hasLangTs(content)) {
    console.log(`✓ 已处理: ${relativePath}`);
    return;
  }
  
  // 提取 script 内容
  const scriptContent = extractScriptBlock(content);
  if (!scriptContent) {
    console.log(`- 无 script 块: ${relativePath}`);
    return;
  }
  
  // 检查是否已有 <script setup> 但没有 lang="ts"
  if (hasScriptSetup(content)) {
    // 只需要添加 lang="ts"
    content = content.replace(/<script\s+setup[^>]*>/, '<script setup lang="ts">');
    fs.writeFileSync(filePath, content, 'utf-8');
    console.log(`✓ 添加 lang="ts": ${relativePath}`);
    return;
  }
  
  // 普通 <script> -> <script setup lang="ts">
  // 移除 export default { ... } 包装
  let newScript = scriptContent;
  
  // 处理 export default
  const exportMatch = newScript.match(/export\s+default\s*\{([\s\S]*)\}/);
  if (exportMatch) {
    newScript = exportMatch[1].trim();
  }
  
  // 移除尾部的分号和逗号
  newScript = newScript.replace(/^[\s,;]*/, '').replace(/[\s,;]*$/, '');
  
  // 移除 name 属性
  newScript = newScript.replace(/name\s*:\s*['"][^'"]*['"]\s*,?\s*/g, '');
  
  // 移除 components 注册
  newScript = newScript.replace(/components\s*:\s*\{[\s\S]*?\}\s*,?\s*/g, '');
  
  // 处理 props
  if (hasDefineProps(newScript)) {
    // 已经有 defineProps，保留
  } else {
    const propsMatch = newScript.match(/props\s*:\s*\{([\s\S]*?)\}\s*,?\s*/);
    if (propsMatch) {
      // 提取 prop 名称和类型
      const propDefs = propsMatch[1];
      const propEntries = [];
      const propRegex = /(\w+)\s*:\s*\{[\s\S]*?type\s*:\s*(\w+)[\s\S]*?required\s*:\s*(true|false)[\s\S]*?default\s*:\s*([^,\n]+)[\s\S]*?\}/g;
      let m;
      while ((m = propRegex.exec(propDefs)) !== null) {
        propEntries.push({ name: m[1], type: m[2], required: m[3] === 'true', default: m[4] });
      }
      
      // 如果没有匹配到完整模式，尝试简单模式
      if (propEntries.length === 0) {
        const simpleRegex = /(\w+)\s*:\s*\{[\s\S]*?type\s*:\s*(\w+)[\s\S]*?\}/g;
        while ((m = simpleRegex.exec(propDefs)) !== null) {
          propEntries.push({ name: m[1], type: m[2], required: false, default: undefined });
        }
      }
      
      if (propEntries.length > 0) {
        let interface_ = `interface Props {\n`;
        for (const prop of propEntries) {
          let tsType = mapVueTypeToTS(prop.type);
          if (prop.required) {
            interface_ += `  ${prop.name}: ${tsType}\n`;
          } else {
            interface_ += `  ${prop.name}?: ${tsType}\n`;
          }
        }
        interface_ += `}\n\n`;
        
        // 替换 props 定义
        newScript = newScript.replace(/props\s*:\s*\{[\s\S]*?\}\s*,?\s*/m, '');
        newScript = interface_ + newScript;
        newScript = `const props = defineProps<Props>()\n` + newScript;
      } else {
        // 无法解析 props，保留原始定义但转为 defineProps
        newScript = newScript.replace(/props\s*:\s*\{([\s\S]*?)\}\s*,?\s*/m, (match, p1) => {
          return `const props = defineProps({\n${p1}\n})\n`;
        });
      }
    }
  }
  
  // 处理 emits
  if (hasDefineEmits(newScript)) {
    // 已经有 defineEmits
  } else {
    const emitsMatch = newScript.match(/emits\s*:\s*\[([\s\S]*?)\]\s*,?\s*/);
    if (emitsMatch) {
      const emitNames = emitsMatch[1].split(',').map(s => s.trim().replace(/['"]/g, ''));
      let emitType = `interface Emits {\n`;
      for (const name of emitNames) {
        emitType += `  (e: '${name}', ...args: unknown[]): void\n`;
      }
      emitType += `}\n\n`;
      
      newScript = newScript.replace(/emits\s*:\s*\[[\s\S]*?\]\s*,?\s*/m, '');
      newScript = emitType + newScript;
      newScript = `const emit = defineEmits<Emits>()\n` + newScript;
    }
  }
  
  // 处理 setup(props, ctx) 或 setup() 函数
  newScript = newScript.replace(/setup\s*\(\s*props\s*,\s*\{([^}]*)\}\s*\)\s*\{([\s\S]*?)\}\s*\)?\s*,?\s*/m, (match, ctxParams, body) => {
    // 提取 emit 和 attrs 等
    return body.trim();
  });
  
  newScript = newScript.replace(/setup\s*\(\s*\)\s*\{([\s\S]*?)\}\s*,?\s*/m, (match, body) => {
    return body.trim();
  });
  
  // 移除 return { ... } 语句（在 setup 中不需要）
  newScript = newScript.replace(/return\s*\{[\s\S]*?\}\s*;?\s*/m, '');
  
  // 清理多余的空行
  newScript = newScript.replace(/\n{3,}/g, '\n\n').trim();
  
  // 替换 script 标签
  content = replaceScriptTag(content, newScript, true);
  
  fs.writeFileSync(filePath, content, 'utf-8');
  console.log(`✓ 已转换: ${relativePath}`);
}

// 主函数
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
  
  console.log('\n转换完成！');
}

main();
