import AIModelManager from '@/views/AIModelManager.vue';
import { createRouter, createWebHistory } from 'vue-router';
import { ElLoading } from 'element-plus';

// 路由懒加载
const Login = () => import('@/views/Login.vue');
const Dashboard = () => import('@/views/Dashboard.vue');
const DataSources = () => import('@/views/DataSources.vue');
const Logs = () => import('@/views/Logs.vue');
const Conversation = () => import('@/views/conversations/Conversation.vue');
const Settings = () => import('@/views/Settings.vue');
const Marketplace = () => import('@/views/Marketplace.vue');
const BriefingHistory = () => import('@/views/briefings/BriefingHistory.vue');  // 取消注释并确认路径
const BriefingDetail = () => import('@/views/briefings/BriefingDetail.vue');
const PriorityDetail = () => import('@/views/priority/PriorityDetail.vue');
const NotFound = () => import('@/views/NotFound.vue');
const Register = () => import('@/views/Register.vue');
const Console = () => import('@/ui/workspace/Console.vue');
const TraceView = () => import('@/views/TraceView.vue');
const Workspace = () => import('@/ui/workspace/Workspace.vue');

// 定义路由
const routes = [
  {
    path: '/',
    redirect: '/workspace'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false, title: '登录' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true, title: '仪表盘' }
  },
  {
    path: '/data-sources',
    name: 'DataSources',
    component: DataSources,
    meta: { requiresAuth: true, title: '数据源管理' }
  },
  {
    path: '/briefings',
    name: 'BriefingHistory',
    component: BriefingHistory,
    meta: { requiresAuth: true, title: '简报历史' }
  },
  {
    path: '/briefings/:id',
    name: 'BriefingDetail',
    component: BriefingDetail,
    meta: { requiresAuth: true, title: '简报详情' }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: Logs,
    meta: { requiresAuth: true, title: '审计日志' }
  },
  {
    path: '/conversations',
    name: 'Conversation',
    component: Conversation,
    meta: { requiresAuth: true, title: '对话详情' }
  },
  
  {
    path: '/priority/:id',
    name: 'PriorityDetail',
    component: PriorityDetail,
    meta: { requiresAuth: true, title: '事项详情' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: { requiresAuth: true, title: '系统设置' }
  },
  {
    path: '/marketplace',
    name: 'Marketplace',
    component: Marketplace,
    meta: { requiresAuth: true, title: '场景商店' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { requiresAuth: false, title: '页面不存在' }
  },
  {
    path: '/models',
    name: 'AIModelManager',
    component: AIModelManager,
    meta: { requiresAuth: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { requiresAuth: false, title: '注册' }
  },
  {
    path: '/console',
    name: 'Console',
    component: Console,
    meta: { requiresAuth: true, title: 'AI控制台' }
  },
  {
    path: '/trace',
    name: 'TraceView',
    component: TraceView,
    meta: { requiresAuth: true, title: 'Trace查看器' }
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: Workspace,
    meta: { requiresAuth: true, title: 'AI工作台', layout: 'blank' }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else {
      return { top: 0 };
    }
  }
});

// 全局前置守卫：认证检查 + 页面标题
router.beforeEach(async (to, from, next) => {
    // 🔧 开发模式：绕过所有认证
  const isDevBypass = true; // 上线前改为 false
  if (isDevBypass) {
    next();
    return;
  }
  
  const loading = ElLoading.service({
    fullscreen: true,
    text: '加载中...',
    background: 'rgba(0, 0, 0, 0.7)'
  });

  document.title = to.meta.title ? `Nova - ${to.meta.title}` : 'Nova';

  console.log('🚦 路由守卫:', to.path, 'from:', from.path);

  // 直接导入 authStore（此时 pinia 已在 main.js 中初始化）
  const { useAuthStore } = await import('@/stores/auth');
  const authStore = useAuthStore();

  // 如果 token 存在但用户信息缺失，尝试重新初始化（防御性）
  if (authStore.token && !authStore.user) {
    await authStore.init().catch(err => console.error('初始化用户信息失败', err));
  }

  const isAuthenticated = authStore.isAuthenticated;
  console.log('🔐 isAuthenticated:', isAuthenticated, 'token:', authStore.token, 'user:', authStore.user);

  if (to.meta.requiresAuth && !isAuthenticated) {
    // 需要登录但未登录，跳转到登录页，并携带原路径
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if (to.name === 'Login' && isAuthenticated) {
    // 已登录访问登录页，重定向到工作台
    next({ name: 'Workspace' });
  } else {
    next();
  }

  setTimeout(() => loading.close(), 100);
});

// 全局后置守卫：关闭加载（可选）
router.afterEach(() => {
  // 可以在这里做其他清理工作
});

export default router;