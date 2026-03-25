<template>
  <el-header class="navbar">
    <div class="navbar-left">
      <el-button :icon="Menu" text @click="emit('toggle-sidebar')" class="menu-toggle" />
      <div class="logo">
        <img v-if="logoUrl" :src="logoUrl" alt="Logo" />
        <span v-else class="logo-text">{{ title }}</span>
      </div>
    </div>

    <div class="navbar-right">
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" :src="userAvatar" :alt="userName">
            {{ userInitial }}
          </el-avatar>
          <span class="user-name">{{ userName }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人资料</el-dropdown-item>
            <el-dropdown-item command="settings">系统设置</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </el-header>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { Menu, ArrowDown } from '@element-plus/icons-vue';

const props = defineProps({
  title: {
    type: String,
    default: 'Nova'
  },
  logoUrl: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['toggle-sidebar', 'logout']);

const authStore = useAuthStore();
const router = useRouter();

const userName = computed(() => authStore.user?.name || authStore.user?.email || '用户');
const userAvatar = computed(() => authStore.user?.avatar || '');
const userInitial = computed(() => (userName.value ? userName.value.charAt(0).toUpperCase() : 'U'));

const handleCommand = (command) => {
  if (command === 'profile') {
    router.push('/settings?tab=profile');
  } else if (command === 'settings') {
    router.push('/settings');
  } else if (command === 'logout') {
    authStore.logout().then(() => {
      emit('logout');
      router.push('/login');
    });
  }
};
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 60px;
  padding: 0 20px;
  background-color: #fff;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-toggle {
  font-size: 20px;
}

.logo {
  display: flex;
  align-items: center;
}
.logo img {
  height: 32px;
}
.logo-text {
  font-size: 20px;
  font-weight: bold;
  color: #1f2937;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 24px;
  transition: background-color 0.2s;
}
.user-info:hover {
  background-color: #f3f4f6;
}

.user-name {
  font-size: 14px;
  color: #374151;
}
</style>