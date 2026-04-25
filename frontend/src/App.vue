<template>
  <div id="app">
    <!-- 强制 Workspace 全屏显示 -->
    <template v-if="$route.path === '/workspace' || $route.meta.layout === 'blank' || isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </template>

    <!-- 其他页面使用后台布局 -->
    <template v-else>
      <NavBar @toggle-sidebar="toggleSidebar" @logout="handleLogout" />
      <SideMenu
        :collapsed="sidebarCollapsed"
        @update:collapsed="sidebarCollapsed = $event as boolean"
        @navigate="handleNavigate as (...args: unknown[]) => void"
      />

      <div class="main-content" :class="{ 'collapsed': sidebarCollapsed }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import NavBar from '@/interface/components/common/NavBar.vue';
import SideMenu from '@/interface/components/common/SideMenu.vue';
import { useAuthStore } from '@/stores/auth';


const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

// 侧边栏折叠状态，持久化到 localStorage
const sidebarCollapsed = ref<boolean>(localStorage.getItem('sidebarCollapsed') === 'true');

watch(sidebarCollapsed, (val: boolean) => {
  localStorage.setItem('sidebarCollapsed', String(val));
});


// 判断当前是否在认证页面（登录或注册）或Console页面或Workspace页面
const isAuthPage = computed(() => {
  return route.name === 'Login' || route.name === 'Register' || route.name === 'Console' || route.name === 'Workspace' || route.path === '/workspace';
});

// 切换侧边栏（由 NavBar 触发）
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value;
};

// 处理路由跳转（可选，用于埋点等）
const handleNavigate = (path: string) => {
  // 可以在这里添加页面访问统计等逻辑
};


// 退出登录（由 NavBar 触发）
const handleLogout = async () => {
  try {
    await authStore.logout();
    // 退出后重定向到登录页
    router.push('/login');
  } catch (error) {
    console.error('退出登录失败:', error);
  }
};
</script>

<style>
/* 全局过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 主内容区域，避开侧边栏宽度 */
.main-content {
  margin-left: 240px;
  transition: margin-left 0.2s ease;
  min-height: 100vh;
  background-color: var(--el-bg-color-page);
}

.main-content.collapsed {
  margin-left: 64px;
}

/* 响应式：小屏幕时侧边栏自动隐藏或悬浮（可选） */
@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }
  .main-content.collapsed {
    margin-left: 0;
  }
}
</style>
