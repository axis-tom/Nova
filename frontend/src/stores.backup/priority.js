import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const usePriorityStore = defineStore('priority', () => {
  // 状态
  const items = ref([]);          // 优先级事项列表
  const loading = ref(false);
  const error = ref(null);

  // 计算属性（假设 Dashboard 使用了这些）
  const highPriorityItems = computed(() => items.value.filter(item => item.priority === '高'));
  const mediumPriorityItems = computed(() => items.value.filter(item => item.priority === '中'));
  const lowPriorityItems = computed(() => items.value.filter(item => item.priority === '低'));

  // 方法：获取优先级事项（示例，可替换为真实 API）
  const fetchItems = async () => {
    loading.value = true;
    try {
      // 模拟 API 调用，实际可替换为 client.get('/api/v1/priority')
      const response = await fetch('/api/v1/priority');
      const data = await response.json();
      items.value = data.items || [];
    } catch (err) {
      error.value = err.message;
      console.error('获取优先级事项失败', err);
    } finally {
      loading.value = false;
    }
  };

  // 可选：其他方法（如 addItem, updateItem, deleteItem），根据 Dashboard 实际需要补充

  return {
    items,
    loading,
    error,
    highPriorityItems,
    mediumPriorityItems,
    lowPriorityItems,
    fetchItems,
  };
});