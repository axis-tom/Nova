<template>
  <el-card class="briefing-preview" :body-style="{ padding: '0' }">
    <template #header>
      <div class="card-header">
        <span class="title">{{ title }}</span>
        <el-button v-if="showMore" link @click="handleMore">{{ moreText }}</el-button>
      </div>
    </template>
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="!briefing" class="empty-state">
      <el-empty :description="emptyText" :image-size="80" />
    </div>
    <div v-else class="preview-content">
      <div class="preview-header">
        <div class="briefing-date">{{ formatDate(briefing.date) }}</div>
        <el-tag v-if="briefing.summary" type="info" size="small" effect="plain">
          {{ briefing.summary }}
        </el-tag>
      </div>
      <div class="preview-body">
        <div class="briefing-title">{{ briefing.title || '今日简报' }}</div>
        <div class="briefing-summary">{{ truncateSummary(briefing.content) }}</div>
      </div>
      <div class="preview-footer">
        <el-button type="primary" link @click="handleViewDetail">
          查看详情
          <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button v-if="showActions" :icon="Download" link @click="handleExport">
          导出
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue';
import { ElCard, ElButton, ElTag, ElSkeleton, ElEmpty, ElIcon } from 'element-plus';
import { ArrowRight, Download } from '@element-plus/icons-vue';
import { formatDate, truncate } from '@/utils/format';

const props = defineProps({
  title: {
    type: String,
    default: '最新简报'
  },
  briefing: {
    type: Object,
    default: null
    // 期望结构: { id, date, title, content, summary }
  },
  loading: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无简报'
  },
  showMore: {
    type: Boolean,
    default: true
  },
  moreText: {
    type: String,
    default: '查看全部'
  },
  showActions: {
    type: Boolean,
    default: true
  },
  maxSummaryLength: {
    type: Number,
    default: 150
  }
});

const emit = defineEmits(['more', 'view-detail', 'export']);

const truncateSummary = (text) => {
  if (!text) return '';
  return truncate(text, props.maxSummaryLength);
};

const formatBriefingDate = (dateStr) => {
  if (!dateStr) return '';
  return formatDate(dateStr, 'YYYY年MM月DD日');
};

const handleMore = () => {
  emit('more');
};

const handleViewDetail = () => {
  emit('view-detail', props.briefing);
};

const handleExport = () => {
  emit('export', props.briefing);
};
</script>

<style scoped>
.briefing-preview {
  border-radius: 12px;
  height: 100%;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 0;
}
.card-header .title {
  font-size: 16px;
  font-weight: 500;
  color: #1f2937;
}

.loading-container,
.empty-state {
  padding: 20px;
}

.preview-content {
  padding: 0 20px 20px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.briefing-date {
  font-size: 14px;
  color: #6b7280;
}

.preview-body {
  margin-bottom: 16px;
}

.briefing-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
  line-height: 1.4;
}

.briefing-summary {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
}

.preview-footer {
  display: flex;
  gap: 16px;
  justify-content: flex-end;
}
</style>