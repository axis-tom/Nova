import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';          // Element Plus 默认样式
import '@/assets/css/main.css';                 // 全局自定义样式
import router from './router';
import App from './App.vue';

// 引入 Element Plus 图标（可选，按需注册）
import * as ElementPlusIconsVue from '@element-plus/icons-vue';
import { useAuthStore } from './stores/auth';

const app = createApp(App);

// 注册 Element Plus 所有图标（如果使用图标组件）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

app.use(createPinia());    // Pinia 状态管理
app.use(router);           // Vue Router
app.use(ElementPlus);      // Element Plus UI 库

// 应用挂载前，初始化认证状态（等待 init 完成）
const authStore = useAuthStore();
authStore.init().then(() => {
  app.mount('#app');
});
