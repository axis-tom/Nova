import { createRouter, createWebHistory } from 'vue-router';
import { ElLoading } from 'element-plus';

// 路由懒加载
const Login = () => import('@/views/Login.vue');
const Dashboard = () => import('@/views/Dashboard.vue');
const DataSources = () => import('@/views/DataSources.vue');
// const BriefingHistory = () => import('@/views/BriefingHistory.vue');
const Logs = () => import('@/views/Logs.vue');
// const ConversationHistory = () => import('@/views/ConversationHistory.vue');
const Settings = () => import('@/views/Settings.vue');
const Marketplace = () => import('@/views/Marketplace.vue');
const BriefingHistory = () => import('@/views/briefings/BriefingHistory.vue');
const ConversationHistory = () => import('@/views/conversations/ConversationHistory.vue');

// 动态路由（带参数）
const BriefingDetail = () => import('@/views/briefings/BriefingDetail.vue');      // 假设有详情页
const ConversationDetail = () => import('@/views/conversations/ConversationDetail.vue'); // 假设有对话详情页
const PriorityDetail = () => import('@/views/priority/PriorityDetail.vue');       // 优先级详情

// 定义路由
const routes = [
  {
    path: '/',
    redirect: '/dashboard'
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
    name: 'ConversationHistory',
    component: ConversationHistory,
    meta: { requiresAuth: true, title: '对话历史' }
  },
  {
    path: '/conversations/:id',
    name: 'ConversationDetail',
    component: ConversationDetail,
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
  // 显示加载效果（可选）
  const loading = ElLoading.service({
    fullscreen: true,
    text: '加载中...',
    background: 'rgba(0, 0, 0, 0.7)'
  });

  // 设置页面标题
  document.title = to.meta.title ? `Nova - ${to.meta.title}` : 'Nova';

  console.log('🚦 路由守卫:', to.path, 'from:', from.path);

  // 获取认证状态
  const { useAuthStore } = await import('@/stores/auth');
  const authStore = useAuthStore();

  console.log('🔐 isAuthenticated:', authStore.isAuthenticated, 'token:', authStore.token);

  // 如果还没有初始化用户信息且 token 存在，尝试自动获取用户信息
  // if (!authStore.user && authStore.token) {
  //   await authStore.init();
  // }
  if (!authStore.user && authStore.token) {
  try {
    await authStore.init();
  } catch (err) {
    console.error('初始化用户信息失败（可能后端未实现 /me）', err);
    // 可选：清除无效 token
    // authStore.logout();
  }
}

  const isAuthenticated = authStore.isAuthenticated;

  if (to.meta.requiresAuth && !isAuthenticated) {
    // 需要登录但未登录，跳转到登录页，并携带原路径
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if (to.name === 'Login' && isAuthenticated) {
    // 已登录访问登录页，重定向到仪表盘
    next({ name: 'Dashboard' });
  } else {
    next();
  }

  // 关闭加载效果（路由切换完成后）
  setTimeout(() => loading.close(), 100);
});

// 全局后置守卫：关闭加载（可选）
router.afterEach(() => {
  // 可以在这里做其他清理工作
});

export default router;