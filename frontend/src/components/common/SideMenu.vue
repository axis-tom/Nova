<template>
  <aside :class="['side-menu', { collapsed }]">
    <div class="menu-header">
      <div class="logo" v-if="!collapsed">
        <img v-if="logoUrl" :src="logoUrl" alt="Logo" />
        <span v-else>{{ title }}</span>
      </div>
      <el-button :icon="collapseIcon" text @click="toggleCollapse" class="collapse-btn" />
    </div>

    <el-menu
      :default-active="activePath"
      :collapse="collapsed"
      :collapse-transition="false"
      router
      class="menu-nav"
    >
      <el-menu-item
        v-for="item in menuItems"
        :key="item.path"
        :index="item.path"
        @click="handleNavigate(item.path)"
      >
        <el-icon><component :is="item.iconComponent" /></el-icon>
        <template #title>{{ item.label }}</template>
      </el-menu-item>
    </el-menu>
  </aside>
</template>

<script setup>
import { Cpu } from '@element-plus/icons-vue'
import { ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import {
  DataBoard,
  Folder,
  Document,
  Tickets,
  ChatLineRound,
  Setting,
  ShoppingCart,
  Fold,
  Expand
} from '@element-plus/icons-vue';

const props = defineProps({
  title: {
    type: String,
    default: 'Nova'
  },
  logoUrl: {
    type: String,
    default: ''
  },
  // 菜单项：{ path, label, iconComponent }
  items: {
    type: Array,
    default: () => [
      { path: '/dashboard', label: '仪表盘', iconComponent: DataBoard },
      { path: '/data-sources', label: '数据源', iconComponent: Folder },
      { path: '/briefings', label: '简报', iconComponent: Document },
      { path: '/logs', label: '审计日志', iconComponent: Tickets },
      { path: '/conversations', label: '对话', iconComponent: ChatLineRound },
      { path: '/settings', label: '设置', iconComponent: Setting },
      { path: '/marketplace', label: '场景商店', iconComponent: ShoppingCart },
      { path: '/models', label: '模型管理', iconComponent: Cpu }
    ]
  },
  collapsed: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:collapsed', 'navigate']);

const route = useRoute();
const activePath = computed(() => route.path);
const collapsed = ref(props.collapsed);
const collapseIcon = computed(() => (collapsed.value ? Expand : Fold));
const menuItems = computed(() => props.items);

const toggleCollapse = () => {
  collapsed.value = !collapsed.value;
  emit('update:collapsed', collapsed.value);
};

const handleNavigate = (path) => {
  emit('navigate', path);
};
</script>

<style scoped>
.side-menu {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 240px;
  background-color: #fff;
  border-right: 1px solid #e5e7eb;
  transition: width 0.2s ease;
  display: flex;
  flex-direction: column;
  z-index: 20;
}

.side-menu.collapsed {
  width: 64px;
}

.menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  height: 60px;
  border-bottom: 1px solid #e5e7eb;
}

.logo {
  font-weight: bold;
  font-size: 18px;
  color: #1f2937;
  overflow: hidden;
  white-space: nowrap;
}
.logo img {
  height: 28px;
}

.collapse-btn {
  font-size: 18px;
}

.menu-nav {
  flex: 1;
  border-right: none;
  overflow-y: auto;
}

/* 覆盖 Element Plus 默认样式以适配折叠效果 */
.menu-nav:not(.el-menu--collapse) {
  width: 100%;
}

.menu-nav.el-menu--collapse {
  width: 100%;
}

/* 菜单项图标居中 */
.menu-nav .el-menu-item [class^="el-icon"] {
  font-size: 20px;
  margin-right: 12px;
}
.menu-nav.el-menu--collapse .el-menu-item [class^="el-icon"] {
  margin-right: 0;
}
</style>