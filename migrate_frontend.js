/**
 * Frontend File Migration Script
 * 
 * Moves files according to the mapping and fixes import paths.
 * 
 * Usage: node migrate_frontend.js
 */

const fs = require('fs');
const path = require('path');

const FRONTEND_SRC = path.join(__dirname, 'frontend', 'src');

// ============================================================
// 1. FILE MOVE MAPPINGS (based on actual file structure)
// ============================================================

const fileMoves = [
  // Stores -> State
  { from: 'stores/console.js', to: 'state/console.js' },
  { from: 'stores/dashboard.js', to: 'state/dashboard.js' },
  { from: 'stores/workspace.js', to: 'state/workspace.js' },

  // Features/voe -> Events
  { from: 'features/voe/dispatcher.js', to: 'events/dispatcher.js' },
  { from: 'features/voe/eventBus.js', to: 'events/eventBus.js' },
  { from: 'features/voe/eventTypes.js', to: 'events/eventTypes.js' },
  { from: 'features/voe/index.js', to: 'events/index.js' },
  { from: 'features/voe/integration-example.js', to: 'events/integration-example.js' },
  { from: 'features/voe/README.md', to: 'events/README.md' },
  { from: 'features/voe/test-voe-system.js', to: 'events/test-voe-system.js' },
  { from: 'features/voe/bridge/graphBridge.js', to: 'events/bridge/graphBridge.js' },
  { from: 'features/voe/bridge/resultBridge.js', to: 'events/bridge/resultBridge.js' },
  { from: 'features/voe/bridge/uiBridge.js', to: 'events/bridge/uiBridge.js' },
  { from: 'features/voe/listeners/graphListener.js', to: 'events/listeners/graphListener.js' },
  { from: 'features/voe/listeners/nodeListener.js', to: 'events/listeners/nodeListener.js' },
  { from: 'features/voe/listeners/uiListener.js', to: 'events/listeners/uiListener.js' },
  { from: 'features/voe/utils/helpers.js', to: 'events/utils/helpers.js' },

  // Features/result -> rendering/result-renderer
  { from: 'features/result/ResultContainer.vue', to: 'rendering/result-renderer/ResultContainer.vue' },
  { from: 'features/result/ResultRenderer.vue', to: 'rendering/result-renderer/ResultRenderer.vue' },
  { from: 'features/result/integration-example.vue', to: 'rendering/result-renderer/integration-example.vue' },
  { from: 'features/result/test-result-system.js', to: 'rendering/result-renderer/test-result-system.js' },
  { from: 'features/result/README.md', to: 'rendering/result-renderer/README.md' },
  { from: 'features/result/parser/resultParser.js', to: 'rendering/result-renderer/parser/resultParser.js' },
  { from: 'features/result/editor/EditToolbar.vue', to: 'rendering/result-renderer/editor/EditToolbar.vue' },
  { from: 'features/result/editor/InlineEditor.vue', to: 'rendering/result-renderer/editor/InlineEditor.vue' },
  { from: 'features/result/renderers/ChartRenderer.vue', to: 'rendering/result-renderer/renderers/ChartRenderer.vue' },
  { from: 'features/result/renderers/ImageCompareRenderer.vue', to: 'rendering/result-renderer/renderers/ImageCompareRenderer.vue' },
  { from: 'features/result/renderers/MarkdownRenderer.vue', to: 'rendering/result-renderer/renderers/MarkdownRenderer.vue' },
  { from: 'features/result/renderers/TableRenderer.vue', to: 'rendering/result-renderer/renderers/TableRenderer.vue' },
  { from: 'features/result/renderers/TextRenderer.vue', to: 'rendering/result-renderer/renderers/TextRenderer.vue' },

  // API files - conversation.js -> conversations.js (rename)
  { from: 'api/conversation.js', to: 'api/conversations.js' },

  // Views -> interface/views
  { from: 'views/Dashboard.vue', to: 'interface/views/Dashboard.vue' },
  { from: 'views/DataSources.vue', to: 'interface/views/DataSources.vue' },
  { from: 'views/Logs.vue', to: 'interface/views/Logs.vue' },
  { from: 'views/Settings.vue', to: 'interface/views/Settings.vue' },
  { from: 'views/Marketplace.vue', to: 'interface/views/Marketplace.vue' },
  { from: 'views/TraceView.vue', to: 'interface/views/TraceView.vue' },
  { from: 'views/AIModelManager.vue', to: 'interface/views/AIModelManager.vue' },
  { from: 'views/Login.vue', to: 'interface/views/Login.vue' },
  { from: 'views/Register.vue', to: 'interface/views/Register.vue' },
  { from: 'views/NotFound.vue', to: 'interface/views/NotFound.vue' },
  { from: 'views/conversations/Conversation.vue', to: 'interface/views/Conversation.vue' },
  { from: 'views/briefings/BriefingHistory.vue', to: 'interface/views/BriefingHistory.vue' },
  { from: 'views/briefings/BriefingDetail.vue', to: 'interface/views/BriefingDetail.vue' },
  { from: 'views/priority/PriorityDetail.vue', to: 'interface/views/PriorityDetail.vue' },

  // ui/chat -> interface/components/chat
  { from: 'ui/chat/ChatWindow.vue', to: 'interface/components/chat/ChatWindow.vue' },
  { from: 'ui/chat/InputArea.vue', to: 'interface/components/chat/InputArea.vue' },
  { from: 'ui/chat/MessageBubble.vue', to: 'interface/components/chat/MessageBubble.vue' },

  // ui/dashboard -> interface/components/dashboard
  { from: 'ui/dashboard/StatsCard.vue', to: 'interface/components/dashboard/StatsCard.vue' },
  { from: 'ui/dashboard/PriorityList.vue', to: 'interface/components/dashboard/PriorityList.vue' },
  { from: 'ui/dashboard/BriefingPreview.vue', to: 'interface/components/dashboard/BriefingPreview.vue' },

  // ui/console -> interface/components/console
  { from: 'ui/console/ConsolePanel.vue', to: 'interface/components/console/ConsolePanel.vue' },
  { from: 'ui/console/DebugPanel.vue', to: 'interface/components/console/DebugPanel.vue' },
  { from: 'ui/console/DebugTools.vue', to: 'interface/components/console/DebugTools.vue' },
  { from: 'ui/console/GraphCanvas.vue', to: 'interface/components/console/GraphCanvas.vue' },
  { from: 'ui/console/RunConsole.vue', to: 'interface/components/console/RunConsole.vue' },
  { from: 'ui/console/TraceGraphIntegration.vue', to: 'interface/components/console/TraceGraphIntegration.vue' },
  { from: 'ui/console/TraceList.vue', to: 'interface/components/console/TraceList.vue' },
  { from: 'ui/console/TraceViewer.vue', to: 'interface/components/console/TraceViewer.vue' },

  // ui/workspace -> interface/components/workspace
  { from: 'ui/workspace/Workspace.vue', to: 'interface/components/workspace/Workspace.vue' },
  { from: 'ui/workspace/Console.vue', to: 'interface/components/workspace/Console.vue' },
  { from: 'ui/workspace/ExecutionCanvas.vue', to: 'interface/components/workspace/ExecutionCanvas.vue' },
  { from: 'ui/workspace/LeftPanel.vue', to: 'interface/components/workspace/LeftPanel.vue' },
  { from: 'ui/workspace/ResultContainer.vue', to: 'interface/components/workspace/ResultContainer.vue' },
  { from: 'ui/workspace/ResultLayer.vue', to: 'interface/components/workspace/ResultLayer.vue' },
  { from: 'ui/workspace/components/TaskLauncher.vue', to: 'interface/components/workspace/components/TaskLauncher.vue' },
  { from: 'ui/workspace/components/ChartPanel.vue', to: 'interface/components/workspace/components/ChartPanel.vue' },
  { from: 'ui/workspace/components/ListingEditor.vue', to: 'interface/components/workspace/components/ListingEditor.vue' },
  { from: 'ui/workspace/components/BusinessNode.vue', to: 'interface/components/workspace/components/BusinessNode.vue' },
  { from: 'ui/workspace/components/StrategyPanel.vue', to: 'interface/components/workspace/components/StrategyPanel.vue' },
  { from: 'ui/workspace/components/ImageCompare.vue', to: 'interface/components/workspace/components/ImageCompare.vue' },

  // ui/common -> interface/components/common
  { from: 'ui/common/LoadingSpinner.vue', to: 'interface/components/common/LoadingSpinner.vue' },
  { from: 'ui/common/NavBar.vue', to: 'interface/components/common/NavBar.vue' },
  { from: 'ui/common/SideMenu.vue', to: 'interface/components/common/SideMenu.vue' },

  // ui/settings -> interface/components/common
  { from: 'ui/settings/DataSourceConfig.vue', to: 'interface/components/common/DataSourceConfig.vue' },
  { from: 'ui/settings/ProfileForm.vue', to: 'interface/components/common/ProfileForm.vue' },
];

// ============================================================
// 2. IMPORT PATH REPLACEMENT RULES
// ============================================================

// Each rule: [searchPattern, replacement]
// The searchPattern is the path prefix to find in import statements
// The replacement is what to replace it with
const importReplacements = [
  // Order matters: more specific first
  ['@/features/result', '@/rendering/result-renderer'],
  ['@/features/voe', '@/events'],
  ['@/stores/', '@/state/'],
  ['@/ui/', '@/interface/components/'],
  ['@/views/', '@/interface/views/'],
  // Also handle non-@/ prefixed imports (relative paths)
  ["'features/result", "'rendering/result-renderer"],
  ["'features/voe", "'events"],
  ["'stores/", "'state/"],
  ["'ui/", "'interface/components/"],
  ["'views/", "'interface/views/"],
];

// ============================================================
// 3. HELPER FUNCTIONS
// ============================================================

function ensureDir(filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function moveFile(fromRel, toRel) {
  const fromAbs = path.join(FRONTEND_SRC, fromRel);
  const toAbs = path.join(FRONTEND_SRC, toRel);

  if (!fs.existsSync(fromAbs)) {
    console.log(`  SKIP (not found): ${fromRel}`);
    return false;
  }

  ensureDir(toAbs);
  fs.renameSync(fromAbs, toAbs);
  console.log(`  MOVED: ${fromRel} -> ${toRel}`);
  return true;
}

function fixImportPaths(fileRel) {
  const fileAbs = path.join(FRONTEND_SRC, fileRel);
  if (!fs.existsSync(fileAbs)) return;

  let content = fs.readFileSync(fileAbs, 'utf-8');
  let originalContent = content;
  const changes = [];

  for (const [search, replace] of importReplacements) {
    // Match in import statements: from '...' or from "..."
    const escapedSearch = search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(from\\s+['"])${escapedSearch}`, 'g');
    let match;
    while ((match = regex.exec(content)) !== null) {
      changes.push(`${match[1]}${search} -> ${match[1]}${replace}`);
    }
    content = content.replace(regex, `$1${replace}`);
  }

  if (content !== originalContent) {
    fs.writeFileSync(fileAbs, content, 'utf-8');
    console.log(`  FIXED imports in: ${fileRel}`);
    for (const change of [...new Set(changes)]) {
      console.log(`       ${change}`);
    }
  }
}

// ============================================================
// 4. MAIN EXECUTION
// ============================================================

console.log('='.repeat(70));
console.log('FRONTEND FILE MIGRATION');
console.log('='.repeat(70));
console.log('');

// Step 1: Move all files
console.log('STEP 1: Moving files...');
console.log('-'.repeat(50));

const movedFiles = [];
for (const move of fileMoves) {
  if (move.from !== move.to) {
    const moved = moveFile(move.from, move.to);
    if (moved) movedFiles.push(move);
  } else {
    const toAbs = path.join(FRONTEND_SRC, move.to);
    ensureDir(toAbs);
    console.log(`  EXISTS: ${move.from}`);
  }
}

console.log('');
console.log('STEP 2: Fixing import paths in all moved files...');
console.log('-'.repeat(50));

for (const move of movedFiles) {
  fixImportPaths(move.to);
}

console.log('');
console.log('STEP 3: Fixing import paths in remaining source files...');
console.log('-'.repeat(50));

const extraFilesToFix = [
  'App.vue',
  'main.js',
  'router/index.js',
];

for (const file of extraFilesToFix) {
  fixImportPaths(file);
}

console.log('');
console.log('STEP 4: Scanning all .js/.vue files for remaining old import paths...');
console.log('-'.repeat(50));

function scanAllFiles(dir) {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      scanAllFiles(fullPath);
    } else if (entry.name.endsWith('.js') || entry.name.endsWith('.vue')) {
      const relPath = path.relative(FRONTEND_SRC, fullPath);
      fixImportPaths(relPath);
    }
  }
}

scanAllFiles(FRONTEND_SRC);

console.log('');
console.log('='.repeat(70));
console.log('MIGRATION COMPLETE');
console.log('='.repeat(70));
