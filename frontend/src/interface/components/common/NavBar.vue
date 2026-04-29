<template>
  <el-header class="navbar">
    <div class="navbar-left">
      <el-button :icon="Menu" text @click="emit('toggle-sidebar')" class="menu-toggle" />
      <div class="logo">
        <img v-if="logoUrl" :src="logoUrl" alt="Logo" />
        <span v-else class="logo-text">{{ title }}</span>
      </div>
    </div>

    <div class="navbar-center">
      <!-- 环境切换组件 -->
      <div class="env-switcher">
        <el-tooltip :content="currentConfig.description" placement="bottom">
          <el-button 
            :type="currentConfig.color" 
            :icon="currentConfig.icon === 'Box' ? Box : Check" 
            size="small"
            @click="showEnvDropdown = !showEnvDropdown"
            class="env-button"
          >
            {{ currentConfig.name }}
          </el-button>
        </el-tooltip>
        
        <!-- 环境下拉菜单 -->
        <div v-if="showEnvDropdown" class="env-dropdown" v-click-outside="closeEnvDropdown">
          <div class="env-dropdown-header">
            <span class="env-dropdown-title">选择环境</span>
            <el-icon class="env-dropdown-close" @click="closeEnvDropdown"><Close /></el-icon>
          </div>
          <div class="env-options">
            <div 
              v-for="(config, key) in envConfig" 
              :key="key"
              class="env-option"
              :class="{ 'active': currentEnv === key }"
              @click="switchEnv(key)"
            >
              <div class="env-option-left">
                <el-icon :size="16" :color="config.color === 'warning' ? '#e6a23c' : '#67c23a'">
                  <component :is="config.icon === 'Box' ? Box : Check" />
                </el-icon>
                <div class="env-option-info">
                  <div class="env-option-name">{{ config.name }}</div>
                  <div class="env-option-desc">{{ config.description }}</div>
                </div>
              </div>
              <el-icon v-if="currentEnv === key" color="#409eff"><Select /></el-icon>
            </div>
          </div>
        </div>
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

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/state/auth';
import { useEnvironmentStore } from '@/state/environment';

import { Menu, ArrowDown, Box, Check, Close, Select } from '@element-plus/icons-vue';

interface Props {
  title?: string
  logoUrl?: string
}

const props = defineProps<Props>();

interface Emits {
  (e: 'toggle-sidebar', ...args: unknown[]): void
  (e: 'logout', ...args: unknown[]): void
}

const emit = defineEmits<Emits>();

const authStore = useAuthStore();
const envStore = useEnvironmentStore();
const router = useRouter();

const showEnvDropdown = ref<boolean>(false);

const userName = computed(() => authStore.user?.name || authStore.user?.email || '用户');
const userAvatar = computed(() => authStore.user?.avatar || '');
const userInitial = computed(() => (userName.value ? userName.value.charAt(0).toUpperCase() : 'U'));

// 环境相关计算属性
const currentEnv = computed(() => envStore.currentEnv);
const currentConfig = computed(() => envStore.currentConfig);
const envConfig = computed(() => envStore.envConfig);

const handleCommand = (command: string) => {
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


// 切换环境
const switchEnv = (env: string) => {
  envStore.switchEnv(env);
  closeEnvDropdown();
};


// 关闭环境下拉菜单
const closeEnvDropdown = () => {
  showEnvDropdown.value = false;
};

// 点击外部关闭下拉菜单的指令
const vClickOutside = {
  mounted(el: HTMLElement, binding: { value: () => void }) {
    (el as HTMLElement & { clickOutsideEvent?: (event: MouseEvent) => void }).clickOutsideEvent = function(this: HTMLElement, event: MouseEvent) {
      if (!(el === event.target || el.contains(event.target as Node))) {
        binding.value();
      }
    };
    document.body.addEventListener('click', (el as HTMLElement & { clickOutsideEvent?: (event: MouseEvent) => void }).clickOutsideEvent!);
  },
  unmounted(el: HTMLElement) {
    document.body.removeEventListener('click', (el as HTMLElement & { clickOutsideEvent?: (event: MouseEvent) => void }).clickOutsideEvent!);
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

.navbar-center {
  display: flex;
  align-items: center;
}

.navbar-right {
  display: flex;
  align-items: center;
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

/* 环境切换器样式 */
.env-switcher {
  position: relative;
}

.env-button {
  font-weight: 500;
}

.env-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  width: 280px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid #e5e7eb;
  z-index: 1000;
  overflow: hidden;
}

.env-dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  background-color: #f9fafb;
}

.env-dropdown-title {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.env-dropdown-close {
  cursor: pointer;
  color: #9ca3af;
  font-size: 16px;
}

.env-dropdown-close:hover {
  color: #6b7280;
}

.env-options {
  padding: 8px;
}

.env-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 4px;
}

.env-option:hover {
  background-color: #f3f4f6;
}

.env-option.active {
  background-color: #eff6ff;
  border: 1px solid #dbeafe;
}

.env-option-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.env-option-info {
  display: flex;
  flex-direction: column;
}

.env-option-name {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  margin-bottom: 2px;
}

.env-option-desc {
  font-size: 12px;
  color: #6b7280;
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
