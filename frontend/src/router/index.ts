import AIModelManager from '@/interface/views/AIModelManager.vue'
import { createRouter, createWebHistory } from 'vue-router'

const Login = () => import('@/interface/views/Login.vue')
const Dashboard = () => import('@/interface/views/Dashboard.vue')
const DataSources = () => import('@/interface/views/DataSources.vue')
const Logs = () => import('@/interface/views/Logs.vue')
const Conversation = () => import('@/interface/views/Conversation.vue')
const Settings = () => import('@/interface/views/Settings.vue')
const Marketplace = () => import('@/interface/views/Marketplace.vue')
const BriefingHistory = () => import('@/interface/views/BriefingHistory.vue')
const BriefingDetail = () => import('@/interface/views/BriefingDetail.vue')
const PriorityDetail = () => import('@/interface/views/PriorityDetail.vue')
const NotFound = () => import('@/interface/views/NotFound.vue')
const Register = () => import('@/interface/views/Register.vue')
const Console = () => import('@/interface/components/workspace/Console.vue')
const TraceView = () => import('@/interface/views/TraceView.vue')
const Workspace = () => import('@/interface/components/workspace/Workspace.vue')

const routes = [
  { path: '/', redirect: '/workspace' },
  { path: '/login', name: 'Login', component: Login, meta: { requiresAuth: false, title: '登录' } },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { requiresAuth: true, title: '仪表盘' } },
  { path: '/data-sources', name: 'DataSources', component: DataSources, meta: { requiresAuth: true, title: '数据源管理' } },
  { path: '/briefings', name: 'BriefingHistory', component: BriefingHistory, meta: { requiresAuth: true, title: '简报历史' } },
  { path: '/briefings/:id', name: 'BriefingDetail', component: BriefingDetail, meta: { requiresAuth: true, title: '简报详情' } },
  { path: '/logs', name: 'Logs', component: Logs, meta: { requiresAuth: true, title: '审计日志' } },
  { path: '/conversations', name: 'Conversation', component: Conversation, meta: { requiresAuth: true, title: '对话详情' } },
  { path: '/priority/:id', name: 'PriorityDetail', component: PriorityDetail, meta: { requiresAuth: true, title: '事项详情' } },
  { path: '/settings', name: 'Settings', component: Settings, meta: { requiresAuth: true, title: '系统设置' } },
  { path: '/marketplace', name: 'Marketplace', component: Marketplace, meta: { requiresAuth: true, title: '场景商店' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/interface/views/NotFound.vue'), meta: { requiresAuth: false, title: '页面不存在' } },
  { path: '/models', name: 'AIModelManager', component: AIModelManager, meta: { requiresAuth: true } },
  { path: '/register', name: 'Register', component: Register, meta: { requiresAuth: false, title: '注册' } },
  { path: '/console', name: 'Console', component: Console, meta: { requiresAuth: true, title: 'AI控制台' } },
  { path: '/trace', name: 'TraceView', component: TraceView, meta: { requiresAuth: true, title: 'Trace查看器' } },
  { path: '/workspace', name: 'Workspace', component: Workspace, meta: { requiresAuth: true, title: 'AI工作台', layout: 'blank' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

router.beforeEach(async (to, from, next) => {
  document.title = to.meta.title ? `Nova - ${to.meta.title}` : 'Nova'

  const { useAuthStore } = await import('@/state/auth')
  const authStore = useAuthStore()

  // 打印当前导航信息，便于诊断
  console.log('[RouterGuard] from:', from.path, '→ to:', to.path, '| name:', to.name)
  console.log('[RouterGuard] isAuthenticated:', authStore.isAuthenticated, '| token:', authStore.token, '| user:', authStore.user)

  // 如果 token 存在但 user 缺失，先尝试加载用户（防御性）
  if (authStore.token && !authStore.user) {
    console.log('[RouterGuard] token 存在但 user 缺失，调用 authStore.init()')
    await authStore.init().catch(err => console.error('初始化用户信息失败', err))
    console.log('[RouterGuard] init 后 → isAuthenticated:', authStore.isAuthenticated, '| user:', authStore.user)
  }

  const isAuthenticated = authStore.isAuthenticated

  // 需要认证的页面，但未登录 → 去登录
  if (to.meta.requiresAuth && !isAuthenticated) {
    console.log('[RouterGuard] 需要认证但未登录，跳转 Login')
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  // 已登录时访问登录页 → 直接去工作台
  if (to.name === 'Login' && isAuthenticated) {
    console.log('[RouterGuard] 已登录访问 Login，重定向到 Workspace')
    return next({ name: 'Workspace' })
  }

  console.log('[RouterGuard] 放行')
  next()
})

export default router