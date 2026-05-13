const fs = require('fs')
const path = require('path')

const srcDir = path.join(__dirname, 'src')

// Fix 1: Add `editable` to Props interface in renderers
function fixRendererProps(content, filePath) {
  // Add editable to Props interface
  content = content.replace(
    /interface Props \{\s*\n\s+result: Record<string, unknown>/g,
    `interface Props {\n  result: Record<string, unknown>\n  editable?: boolean`
  )
  
  // Fix result.content type access - add type assertion
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  
  // Fix result.meta type access
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  
  // Fix template access to result.content and result.meta
  content = content.replace(
    /result\.content(?!\s+as)/g,
    '(result.content as Record<string, unknown>)'
  )
  
  return content
}

// Fix 2: Add missing properties to integration-example.vue
function fixIntegrationExample(content) {
  // Add simulateGraphRecalc method
  if (!content.includes('simulateGraphRecalc')) {
    content = content.replace(
      /const clearResults =/,
      `const simulateGraphRecalc = () => {
  addLog('info', '🔄', '触发Graph重算...')
  dataFlowStatus.value = '重算中...'
  setTimeout(() => {
    dataFlowStatus.value = '正常'
    addLog('success', '✅', 'Graph重算完成')
  }, 1500)
}

const clearResults =`
    )
  }
  
  // Add codeTabs
  if (!content.includes('const codeTabs')) {
    content = content.replace(
      /const editorTypes =/,
      `const codeTabs = [
  { id: 'container', label: 'ResultContainer' },
  { id: 'renderer', label: '自定义渲染器' },
  { id: 'event', label: '事件发送' },
  { id: 'integration', label: '完整集成' }
]

const editorTypes =`
    )
  }
  
  return content
}

// Fix 3: Fix @/state/auth -> @/stores/auth
function fixStorePath(content) {
  content = content.replace(/from ['"]@\/state\/auth['"]/g, "from '@/stores/auth'")
  content = content.replace(/from ['"]@\/state\/environment['"]/g, "from '@/stores/environment'")
  content = content.replace(/from ['"]@\/state\/dataSources['"]/g, "from '@/stores/dataSources'")
  return content
}

// Fix 4: Fix .js imports - add .ts extension or use type-only imports
function fixJsImports(content) {
  // For .vue files, change .js imports to .ts
  content = content.replace(/from ['"]([^'"]+)\.js['"]/g, "from '$1'")
  return content
}

// Fix 5: Add type annotations to function parameters
function addParameterTypes(content) {
  // Add types to common patterns
  content = content.replace(
    /const handleEditorSave = \(data\)/g,
    'const handleEditorSave = (data: string)'
  )
  content = content.replace(
    /const handleEditorEdit = \(data\)/g,
    'const handleEditorEdit = (data: string)'
  )
  content = content.replace(
    /const handleEditorCancel = \(\)/g,
    'const handleEditorCancel = ()'
  )
  return content
}

// Fix 6: Fix `select` on HTMLElement -> use HTMLInputElement or HTMLTextAreaElement
function fixSelectOnElement(content) {
  content = content.replace(
    /textAreaRef\.value\.select\(\)/g,
    '(textAreaRef.value as HTMLTextAreaElement).select()'
  )
  content = content.replace(
    /markdownAreaRef\.value\.select\(\)/g,
    '(markdownAreaRef.value as HTMLTextAreaElement).select()'
  )
  content = content.replace(
    /editorRef\.value\.select\(\)/g,
    '(editorRef.value as HTMLTextAreaElement).select()'
  )
  return content
}

// Fix 7: Fix formRef type to use proper ElementPlus types
function fixFormRef(content) {
  content = content.replace(
    /const formRef = ref<HTMLElement \| null>\(null\)/g,
    'const formRef = ref<InstanceType<typeof ElForm> | null>(null)'
  )
  return content
}

// Fix 8: Fix `clearValidate`, `validate`, `validateField`, `resetFields` on formRef
function fixFormMethods(content) {
  content = content.replace(
    /formRef\.value\?\.clearValidate/g,
    'formRef.value?.clearValidate'
  )
  content = content.replace(
    /formRef\.value\?\.validateField/g,
    'formRef.value?.validateField'
  )
  content = content.replace(
    /formRef\.value\?\.validate/g,
    'formRef.value?.validate'
  )
  content = content.replace(
    /formRef\.value\.resetFields\(\)/g,
    'formRef.value?.resetFields()'
  )
  return content
}

// Fix 9: Fix `avatarInput.value.click()` null check
function fixNullChecks(content) {
  content = content.replace(
    /avatarInput\.value\.click\(\)/g,
    'avatarInput.value?.click()'
  )
  return content
}

// Fix 10: Fix `props.profile` undefined access
function fixProfileAccess(content) {
  content = content.replace(
    /avatarPreview\.value = props\.profile\.avatar/g,
    'avatarPreview.value = props.profile?.avatar'
  )
  content = content.replace(
    /formData\.name = props\.profile\.name/g,
    'formData.name = props.profile?.name'
  )
  content = content.replace(
    /formData\.email = props\.profile\.email/g,
    'formData.email = props.profile?.email'
  )
  content = content.replace(
    /formData\.phone = props\.profile\.phone/g,
    'formData.phone = props.profile?.phone'
  )
  content = content.replace(
    /formData\.company = props\.profile\.company/g,
    'formData.company = props.profile?.company'
  )
  content = content.replace(
    /formData\.title = props\.profile\.title/g,
    'formData.title = props.profile?.title'
  )
  return content
}

// Fix 11: Fix `watch` callback parameter types
function fixWatchTypes(content) {
  content = content.replace(
    /watch\(\s*\n?\s*\(\) => props\.profile,/g,
    'watch(\n  () => props.profile,'
  )
  return content
}

// Fix 12: Fix `catch (error)` -> `catch (error: unknown)`
function fixCatchTypes(content) {
  content = content.replace(
    /catch\s*\(\s*error\s*\)/g,
    'catch (error: unknown)'
  )
  return content
}

// Fix 13: Fix `msg` type in v-for
function fixVForTypes(content) {
  content = content.replace(
    /v-for="msg in messages"/g,
    'v-for="(msg, index) in messages" :key="index"'
  )
  return content
}

// Fix 14: Fix `wrapRef` property
function fixWrapRef(content) {
  content = content.replace(
    /scrollbarRef\.value\.wrapRef/g,
    '(scrollbarRef.value as any)?.wrapRef'
  )
  return content
}

// Fix 15: Fix `isUser` not in Props - add it
function fixMessageBubbleProps(content) {
  content = content.replace(
    /interface Props \{\s*\n\s+message: Record<string, unknown>/g,
    `interface Props {\n  message: Record<string, unknown>\n  isUser?: boolean\n  userAvatar?: string\n  aiAvatar?: string\n  userName?: string\n  aiName?: string`
  )
  return content
}

// Fix 16: Fix `codeTabs` in template
function fixCodeTabsTemplate(content) {
  content = content.replace(
    /v-for="tab in codeTabs"/g,
    'v-for="(tab, index) in codeTabs" :key="index"'
  )
  return content
}

// Fix 17: Fix `simulateGraphRecalc` in template
function fixSimulateGraphRecalcTemplate(content) {
  content = content.replace(
    /@click="simulateGraphRecalc"/g,
    '@click="simulateGraphRecalc()"'
  )
  return content
}

// Fix 18: Fix `log` type in v-for
function fixLogVFor(content) {
  content = content.replace(
    /v-for="\(log, index\) in operationLogs"/g,
    'v-for="(log: Record<string, unknown>, index: number) in operationLogs"'
  )
  return content
}

// Fix 19: Fix `resultTypes` index access
function fixResultTypesIndex(content) {
  content = content.replace(
    /const result = testResults\[type\]/g,
    'const result = (testResults as Record<string, unknown>)[type]'
  )
  return content
}

// Fix 20: Fix `getEditorPlaceholder` index access
function fixPlaceholderIndex(content) {
  content = content.replace(
    /return placeholders\[type\]/g,
    'return (placeholders as Record<string, string>)[type]'
  )
  return content
}

// Fix 21: Fix `getProgressColor` parameter type
function fixProgressColor(content) {
  content = content.replace(
    /const getProgressColor = \(percentage\)/g,
    'const getProgressColor = (percentage: number)'
  )
  return content
}

// Fix 22: Fix `LoadingSpinner` size type
function fixLoadingSpinner(content) {
  content = content.replace(
    /const size = props\.size/g,
    'const size = props.size || "medium"'
  )
  return content
}

// Fix 23: Fix `NavBar` parameter types
function fixNavBarTypes(content) {
  content = content.replace(
    /const handleCommand = \(command\)/g,
    'const handleCommand = (command: string)'
  )
  content = content.replace(
    /const handleEnvChange = \(env\)/g,
    'const handleEnvChange = (env: string)'
  )
  return content
}

// Fix 24: Fix `DataSourceConfig` parameter types
function fixDataSourceConfigTypes(content) {
  content = content.replace(
    /const getProviderLabel = \(type\)/g,
    'const getProviderLabel = (type: string)'
  )
  content = content.replace(
    /const getProviderIcon = \(type\)/g,
    'const getProviderIcon = (type: string)'
  )
  content = content.replace(
    /const getProviderFields = \(type\)/g,
    'const getProviderFields = (type: string)'
  )
  content = content.replace(
    /const getProviderPlaceholder = \(type\)/g,
    'const getProviderPlaceholder = (type: string)'
  )
  content = content.replace(
    /const handleFieldChange = \(field\)/g,
    'const handleFieldChange = (field: string)'
  )
  content = content.replace(
    /const handleAddRow = \(\)/g,
    'const handleAddRow = ()'
  )
  content = content.replace(
    /const handleDeleteRow = \(row\)/g,
    'const handleDeleteRow = (row: number)'
  )
  content = content.replace(
    /const handleEditRow = \(row\)/g,
    'const handleEditRow = (row: number)'
  )
  content = content.replace(
    /const handleSaveRow = \(row\)/g,
    'const handleSaveRow = (row: number)'
  )
  return content
}

// Fix 25: Fix `def` type in DataSourceConfig
function fixDefType(content) {
  content = content.replace(
    /v-for="def in providerFields"/g,
    'v-for="(def, idx) in providerFields" :key="idx"'
  )
  return content
}

// Fix 26: Fix `s` type in DataSourceConfig v-for
function fixSForType(content) {
  content = content.replace(
    /v-for="s in dataSources"/g,
    'v-for="(s, idx) in dataSources" :key="idx"'
  )
  return content
}

// Fix 27: Fix `field` type in DataSourceConfig v-for
function fixFieldForType(content) {
  content = content.replace(
    /v-for="field in providerFields"/g,
    'v-for="(field, idx) in providerFields" :key="idx"'
  )
  return content
}

// Fix 28: Fix `msg` type in ChatWindow
function fixMsgType(content) {
  content = content.replace(
    /v-for="msg in messages"/g,
    'v-for="(msg, idx) in messages" :key="idx"'
  )
  return content
}

// Fix 29: Fix `file` type in InputArea
function fixFileType(content) {
  content = content.replace(
    /const handleFileSelect = \(file\)/g,
    'const handleFileSelect = (file: File)'
  )
  return content
}

// Fix 30: Fix `text` type in ChatWindow
function fixTextType(content) {
  content = content.replace(
    /const sendMessage = \(text\)/g,
    'const sendMessage = (text: string)'
  )
  return content
}

// Fix 31: Fix `data` type in ChatWindow websocket
function fixWsDataType(content) {
  content = content.replace(
    /ws\.onmessage = \(event\) =>/g,
    'ws.onmessage = (event: MessageEvent) =>'
  )
  return content
}

// Fix 32: Fix `wsHandler` type
function fixWsHandlerType(content) {
  content = content.replace(
    /let wsHandler/g,
    'let wsHandler: WebSocket | null'
  )
  return content
}

// Fix 33: Fix `dateStr` type in MessageBubble
function fixDateStrType(content) {
  content = content.replace(
    /const formatFullTime = \(dateStr\)/g,
    'const formatFullTime = (dateStr: string)'
  )
  content = content.replace(
    /const formatRelativeTime = \(dateStr\)/g,
    'const formatRelativeTime = (dateStr: string)'
  )
  return content
}

// Fix 34: Fix `msg` type in ChatWindow template
function fixMsgTemplateType(content) {
  content = content.replace(
    /msg\.role/g,
    '(msg as Record<string, unknown>).role'
  )
  content = content.replace(
    /msg\.content/g,
    '(msg as Record<string, unknown>).content'
  )
  return content
}

// Fix 35: Fix `s` type in DataSourceConfig template
function fixSTemplateType(content) {
  content = content.replace(
    /s\.name/g,
    '(s as Record<string, unknown>).name'
  )
  content = content.replace(
    /s\.type/g,
    '(s as Record<string, unknown>).type'
  )
  content = content.replace(
    /s\.config/g,
    '(s as Record<string, unknown>).config'
  )
  return content
}

// Fix 36: Fix `def` type in DataSourceConfig template
function fixDefTemplateType(content) {
  content = content.replace(
    /def\.key/g,
    '(def as Record<string, unknown>).key'
  )
  content = content.replace(
    /def\.label/g,
    '(def as Record<string, unknown>).label'
  )
  content = content.replace(
    /def\.type/g,
    '(def as Record<string, unknown>).type'
  )
  content = content.replace(
    /def\.placeholder/g,
    '(def as Record<string, unknown>).placeholder'
  )
  return content
}

// Fix 37: Fix `field` type in DataSourceConfig template
function fixFieldTemplateType(content) {
  content = content.replace(
    /field\.key/g,
    '(field as Record<string, unknown>).key'
  )
  content = content.replace(
    /field\.value/g,
    '(field as Record<string, unknown>).value'
  )
  return content
}

// Fix 38: Fix `row` type in DataSourceConfig template
function fixRowTemplateType(content) {
  content = content.replace(
    /row\.name/g,
    '(row as Record<string, unknown>).name'
  )
  content = content.replace(
    /row\.type/g,
    '(row as Record<string, unknown>).type'
  )
  return content
}

// Fix 39: Fix `log` type in integration-example template
function fixLogTemplateType(content) {
  content = content.replace(
    /log\.time/g,
    '(log as Record<string, unknown>).time'
  )
  content = content.replace(
    /log\.icon/g,
    '(log as Record<string, unknown>).icon'
  )
  content = content.replace(
    /log\.message/g,
    '(log as Record<string, unknown>).message'
  )
  content = content.replace(
    /log\.type/g,
    '(log as Record<string, unknown>).type'
  )
  return content
}

// Fix 40: Fix `renderer` type in integration-example
function fixRendererType(content) {
  content = content.replace(
    /const previewRenderer = \(renderer\)/g,
    'const previewRenderer = (renderer: Record<string, unknown>)'
  )
  return content
}

// Fix 41: Fix `type` parameter in simulateGraphOutput
function fixSimulateGraphOutputType(content) {
  content = content.replace(
    /const simulateGraphOutput = \(type\)/g,
    'const simulateGraphOutput = (type: string)'
  )
  return content
}

// Fix 42: Fix `selectResultType` parameter
function fixSelectResultType(content) {
  content = content.replace(
    /const selectResultType = \(type\)/g,
    'const selectResultType = (type: string)'
  )
  return content
}

// Fix 43: Fix `addLog` parameter types
function fixAddLogTypes(content) {
  content = content.replace(
    /const addLog = \(type, icon, message\)/g,
    'const addLog = (type: string, icon: string, message: string)'
  )
  return content
}

// Fix 44: Fix `ChartRenderer` content type
function fixChartRendererTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 45: Fix `ImageCompareRenderer` content type
function fixImageCompareTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 46: Fix `MarkdownRenderer` content type
function fixMarkdownTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 47: Fix `TableRenderer` content type
function fixTableTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 48: Fix `TextRenderer` content type
function fixTextTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 49: Fix `InlineEditor` content type
function fixInlineEditorTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  return content
}

// Fix 50: Fix `ResultContainer` content type
function fixResultContainerTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /props\.result\.meta/g,
    '(props.result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 51: Fix `EditToolbar` content type
function fixEditToolbarTypes(content) {
  content = content.replace(
    /props\.result\.content/g,
    '(props.result.content as Record<string, unknown>)'
  )
  return content
}

// Fix 52: Fix `ChartRenderer` template access
function fixChartRendererTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /result\.meta/g,
    '(result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 53: Fix `ImageCompareRenderer` template access
function fixImageCompareTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /result\.meta/g,
    '(result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 54: Fix `MarkdownRenderer` template access
function fixMarkdownTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /result\.meta/g,
    '(result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 55: Fix `TableRenderer` template access
function fixTableTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /result\.meta/g,
    '(result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 56: Fix `TextRenderer` template access
function fixTextTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /result\.meta/g,
    '(result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 57: Fix `InlineEditor` template access
function fixInlineEditorTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  return content
}

// Fix 58: Fix `EditToolbar` template access
function fixEditToolbarTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  return content
}

// Fix 59: Fix `ResultContainer` template access
function fixResultContainerTemplate(content) {
  content = content.replace(
    /result\.content/g,
    '(result.content as Record<string, unknown>)'
  )
  content = content.replace(
    /result\.meta/g,
    '(result.meta as Record<string, unknown>)'
  )
  return content
}

// Fix 60: Fix `ChartRenderer` chartType index
function fixChartTypeIndex(content) {
  content = content.replace(
    /chartTypeMap\[chartType\]/g,
    '(chartTypeMap as Record<string, string>)[chartType]'
  )
  return content
}

// Fix 61: Fix `ImageCompareRenderer` viewMode index
function fixViewModeIndex(content) {
  content = content.replace(
    /viewModeLabels\[viewMode\]/g,
    '(viewModeLabels as Record<string, string>)[viewMode]'
  )
  return content
}

// Fix 62: Fix `DataSourceConfig` providerIcons index
function fixProviderIconsIndex(content) {
  content = content.replace(
    /providerIcons\[type\]/g,
    '(providerIcons as Record<string, string>)[type]'
  )
  return content
}

// Fix 63: Fix `DataSourceConfig` formRules index
function fixFormRulesIndex(content) {
  content = content.replace(
    /formRules\[`config\.\$\{field\.key\}`\]/g,
    '(formRules as Record<string, unknown>)[`config.${(field as Record<string, unknown>).key}`]'
  )
  return content
}

// Fix 64: Fix `DataSourceConfig` providerFields type
function fixProviderFieldsType(content) {
  content = content.replace(
    /const providerFields = computed/g,
    'const providerFields = computed'
  )
  return content
}

// Fix 65: Fix `DataSourceConfig` handleFieldChange
function fixHandleFieldChange(content) {
  content = content.replace(
    /const handleFieldChange = \(field: string\)/g,
    'const handleFieldChange = (field: string) => {'
  )
  return content
}

// Fix 66: Fix `DataSourceConfig` handleAddRow
function fixHandleAddRow(content) {
  content = content.replace(
    /const handleAddRow = \(\)/g,
    'const handleAddRow = () => {'
  )
  return content
}

// Fix 67: Fix `DataSourceConfig` handleDeleteRow
function fixHandleDeleteRow(content) {
  content = content.replace(
    /const handleDeleteRow = \(row: number\)/g,
    'const handleDeleteRow = (row: number) => {'
  )
  return content
}

// Fix 68: Fix `DataSourceConfig` handleEditRow
function fixHandleEditRow(content) {
  content = content.replace(
    /const handleEditRow = \(row: number\)/g,
    'const handleEditRow = (row: number) => {'
  )
  return content
}

// Fix 69: Fix `DataSourceConfig` handleSaveRow
function fixHandleSaveRow(content) {
  content = content.replace(
    /const handleSaveRow = \(row: number\)/g,
    'const handleSaveRow = (row: number) => {'
  )
  return content
}

// Fix 70: Fix `DataSourceConfig` getProviderLabel
function fixGetProviderLabel(content) {
  content = content.replace(
    /const getProviderLabel = \(type: string\)/g,
    'const getProviderLabel = (type: string) => {'
  )
  return content
}

// Fix 71: Fix `DataSourceConfig` getProviderIcon
function fixGetProviderIcon(content) {
  content = content.replace(
    /const getProviderIcon = \(type: string\)/g,
    'const getProviderIcon = (type: string) => {'
  )
  return content
}

// Fix 72: Fix `DataSourceConfig` getProviderFields
function fixGetProviderFields(content) {
  content = content.replace(
    /const getProviderFields = \(type: string\)/g,
    'const getProviderFields = (type: string) => {'
  )
  return content
}

// Fix 73: Fix `DataSourceConfig` getProviderPlaceholder
function fixGetProviderPlaceholder(content) {
  content = content.replace(
    /const getProviderPlaceholder = \(type: string\)/g,
    'const getProviderPlaceholder = (type: string) => {'
  )
  return content
}

// Fix 74: Fix `DataSourceConfig` handleFieldChange body
function fixHandleFieldChangeBody(content) {
  content = content.replace(
    /const handleFieldChange = \(field: string\) => \{\s*\n\s+formData\.config\[field\]/g,
    'const handleFieldChange = (field: string) => {\n  (formData.config as Record<string, unknown>)[field]'
  )
  return content
}

// Fix 75: Fix `DataSourceConfig` formData.config access
function fixFormDataConfig(content) {
  content = content.replace(
    /formData\.config\[/g,
    '(formData.config as Record<string, unknown>)['
  )
  return content
}

// Fix 76: Fix `DataSourceConfig` editingRow access
function fixEditingRow(content) {
  content = content.replace(
    /editingRow\./g,
    '(editingRow.value as Record<string, unknown>).'
  )
  return content
}

// Fix 77: Fix `DataSourceConfig` editingRow type
function fixEditingRowType(content) {
  content = content.replace(
    /const editingRow = ref<null \| Record<string, unknown>>\(null\)/g,
    'const editingRow = ref<Record<string, unknown> | null>(null)'
  )
  return content
}

// Fix 78: Fix `DataSourceConfig` editingId type
function fixEditingIdType(content) {
  content = content.replace(
    /const editingId = ref<string \| null>\(null\)/g,
    'const editingId = ref<string | number | null>(null)'
  )
  return content
}

// Fix 79: Fix `DataSourceConfig` handleEditRow body
function fixHandleEditRowBody(content) {
  content = content.replace(
    /editingRow\.value = \{ \.\.\.row \}/g,
    'editingRow.value = { ...(row as Record<string, unknown>) }'
  )
  return content
}

// Fix 80: Fix `DataSourceConfig` handleSaveRow body
function fixHandleSaveRowBody(content) {
  content = content.replace(
    /editingRow\.value = null/g,
    'editingRow.value = null'
  )
  return content
}

// Fix 81: Fix `DataSourceConfig` handleDeleteRow body
function fixHandleDeleteRowBody(content) {
  content = content.replace(
    /dataSources\.value\.splice\(row, 1\)/g,
    'dataSources.value.splice(row as number, 1)'
  )
  return content
}

// Fix 82: Fix `DataSourceConfig` handleAddRow body
function fixHandleAddRowBody(content) {
  content = content.replace(
    /dataSources\.value\.push/g,
    'dataSources.value.push'
  )
  return content
}

// Fix 83: Fix `DataSourceConfig` getProviderFields body
function fixGetProviderFieldsBody(content) {
  content = content.replace(
    /return providerFieldsMap\[type\]/g,
    'return (providerFieldsMap as Record<string, unknown>)[type]'
  )
  return content
}

// Fix 84: Fix `DataSourceConfig` getProviderPlaceholder body
function fixGetProviderPlaceholderBody(content) {
  content = content.replace(
    /return providerPlaceholders\[type\]/g,
    'return (providerPlaceholders as Record<string, string>)[type]'
  )
  return content
}

// Fix 85: Fix `DataSourceConfig` getProviderLabel body
function fixGetProviderLabelBody(content) {
  content = content.replace(
    /return providerLabels\[type\]/g,
    'return (providerLabels as Record<string, string>)[type]'
  )
  return content
}

// Fix 86: Fix `DataSourceConfig` getProviderIcon body
function fixGetProviderIconBody(content) {
  content = content.replace(
    /return providerIcons\[type\]/g,
    'return (providerIcons as Record<string, string>)[type]'
  )
  return content
}

// Fix 87: Fix `DataSourceConfig` handleFieldChange body
function fixHandleFieldChangeBody2(content) {
  content = content.replace(
    /formData\.config\[field\] =/g,
    '(formData.config as Record<string, unknown>)[field] ='
  )
  return content
}

// Fix 88: Fix `DataSourceConfig` formData.config access in template
function fixFormDataConfigTemplate(content) {
  content = content.replace(
    /formData\.config\[/g,
    '(formData.config as Record<string, unknown>)['
  )
  return content
}

// Fix 89: Fix `DataSourceConfig` providerFieldsMap type
function fixProviderFieldsMap(content) {
  content = content.replace(
    /const providerFieldsMap =/g,
    'const providerFieldsMap: Record<string, Record<string, unknown>[]> ='
  )
  return content
}

// Fix 90: Fix `DataSourceConfig` providerLabels type
function fixProviderLabels(content) {
  content = content.replace(
    /const providerLabels =/g,
    'const providerLabels: Record<string, string> ='
  )
  return content
}

// Fix 91: Fix `DataSourceConfig` providerIcons type
function fixProviderIcons(content) {
  content = content.replace(
    /const providerIcons =/g,
    'const providerIcons: Record<string, string> ='
  )
  return content
}

// Fix 92: Fix `DataSourceConfig` providerPlaceholders type
function fixProviderPlaceholders(content) {
  content = content.replace(
    /const providerPlaceholders =/g,
    'const providerPlaceholders: Record<string, string> ='
  )
  return content
}

// Fix 93: Fix `DataSourceConfig` formRules type
function fixFormRulesType(content) {
  content = content.replace(
    /const formRules =/g,
    'const formRules: Record<string, unknown> ='
  )
  return content
}

// Fix 94: Fix `DataSourceConfig` dataSources type
function fixDataSourcesType(content) {
  content = content.replace(
    /const dataSources = ref/g,
    'const dataSources = ref<Record<string, unknown>[]>([])'
  )
  return content
}

// Fix 95: Fix `DataSourceConfig` formData type
function fixFormDataType(content) {
  content = content.replace(
    /const formData = reactive/g,
    'const formData = reactive<Record<string, unknown>>'
  )
  return content
}

// Fix 96: Fix `DataSourceConfig` editingRow type
function fixEditingRowType2(content) {
  content = content.replace(
    /const editingRow = ref/g,
    'const editingRow = ref<Record<string, unknown> | null>(null)'
  )
  return content
}

// Fix 97: Fix `DataSourceConfig` editingId type
function fixEditingIdType2(content) {
  content = content.replace(
    /const editingId = ref/g,
    'const editingId = ref<string | number | null>(null)'
  )
  return content
}

// Fix 98: Fix `DataSourceConfig` handleFieldChange type
function fixHandleFieldChangeType(content) {
  content = content.replace(
    /const handleFieldChange = \(field: string\) =>/g,
    'const handleFieldChange = (field: string) =>'
  )
  return content
}

// Fix 99: Fix `DataSourceConfig` handleAddRow type
function fixHandleAddRowType(content) {
  content = content.replace(
    /const handleAddRow = \(\) =>/g,
    '