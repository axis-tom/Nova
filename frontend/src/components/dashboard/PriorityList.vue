<template>
  <el-card class="priority-list">
    <template #header>
      <div class="card-header">
        <span class="title">{{ title }}</span>
        <el-button v-if="showMore" link @click="handleMore">{{ moreText }}</el-button>
      </div>
    </template>
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>
    <div v-else-if="items.length === 0" class="empty-state">
      <el-empty :description="emptyText" :image-size="80" />
    </div>
    <div v-else class="items-list">
      <div
        v-for="item in items"
        :key="item.id"
        class="priority-item"
        @click="handleItemClick(item)"
      >
        <div class="item-priority">
          <el-tag :type="priorityTagType(item.priority)" size="small" effect="light">
            {{ item.priority }}
          </el-tag>
        </div>
        <div class="item-content">
          <div class="item-title">{{ item.title }}</div>
          <div class="item-meta">
            <span class="item-source">{{ item.source }}</span>
            <span class="item-time">{{ formatTime(item.createdAt) }}</span>
          </div>
        </div>
        <div class="item-actions">
          <el-button
            v-if="showActions"
            :icon="Check"
            circle
            size="small"
            type="primary"
            plain
            @click.stop="handleComplete(item)"
          />
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue';
import { ElCard, ElButton, ElTag, ElSkeleton, ElEmpty } from 'element-plus';
import { Check } from '@element-plus/icons-vue';
import { timeAgo } from '@/utils/format';

const props = defineProps({
  title: {
    type: String,
    default: '待处理事项'
  },
  items: {
    type: Array,
    default: () => []
    // 每个 item: { id, priority, title, source, createdAt }
  },
  loading: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无待处理事项'
  },
  showMore: {
    type: Boolean,
    default: true
  },
  moreText: {
    type: String,
    default: '查看更多'
  },
  showActions: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['item-click', 'more', 'complete']);

const priorityTagType = (priority) => {
  const map = {
    '高': 'danger',
    '中': 'warning',
    '低': 'info'
  };
  return map[priority] || 'info';
};

const formatTime = (dateStr) => {
  if (!dateStr) return '';
  return timeAgo(dateStr);
};

const handleItemClick = (item) => {
  emit('item-click', item);
};

const handleMore = () => {
  emit('more');
};

const handleComplete = (item) => {
  emit('complete', item);
};
</script>

<style scoped>
.priority-list {
  border-radius: 12px;
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header .title {
  font-size: 16px;
  font-weight: 500;
  color: #1f2937;
}

.loading-container,
.empty-state {
  padding: 20px 0;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.priority-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background-color: #f9fafb;
  cursor: pointer;
  transition: background-color 0.2s;
}
.priority-item:hover {
  background-color: #f3f4f6;
}

.item-priority {
  flex-shrink: 0;
  width: 48px;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
  word-break: break-word;
}

.item-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.item-source {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}
.priority-item:hover .item-actions {
  opacity: 1;
}
</style>