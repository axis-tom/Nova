<template>
  <div class="marketplace">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">场景商店</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索场景..."
            :prefix-icon="Search"
            clearable
            style="width: 240px"
          />
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="scene in filteredScenes" :key="scene.id">
          <el-card class="scene-card" shadow="hover" @click="installScene(scene)">
            <div class="scene-icon">
              <el-icon :size="48">
                <component :is="scene.icon" />
              </el-icon>
            </div>
            <div class="scene-name">{{ scene.name }}</div>
            <div class="scene-desc">{{ scene.description }}</div>
            <div class="scene-tags">
              <el-tag v-for="tag in scene.tags" :key="tag" size="small">{{ tag }}</el-tag>
            </div>
            <div class="scene-footer">
              <el-button type="primary" size="small" @click.stop="installScene(scene)">
                {{ scene.installed ? '已安装' : '安装' }}
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="filteredScenes.length === 0 && !loading" description="暂无场景" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Search, OfficeBuilding, DataAnalysis, ChatDotRound, Management, Files } from '@element-plus/icons-vue';

const loading = ref(false);
const searchKeyword = ref('');
const scenes = ref([
  {
    id: 1,
    name: '电商运营助手',
    description: '自动监控商品评价、竞品价格，生成销售报告',
    icon: 'ShoppingCart',
    tags: ['电商', '监控', '报告'],
    installed: false
  },
  {
    id: 2,
    name: '自媒体内容管家',
    description: '聚合热点、生成文案、自动发布到多平台',
    icon: 'Edit',
    tags: ['内容', '自媒体', '发布'],
    installed: true
  },
  {
    id: 3,
    name: '财务管理小助手',
    description: '银行流水分析、发票管理、税务提醒',
    icon: 'Money',
    tags: ['财务', '发票', '税务'],
    installed: false
  },
  {
    id: 4,
    name: '客户关系维护',
    description: '邮件跟进、生日提醒、满意度调查',
    icon: 'User',
    tags: ['CRM', '邮件', '提醒'],
    installed: false
  },
  {
    id: 5,
    name: '项目管理看板',
    description: '任务拆解、进度跟踪、团队协作',
    icon: 'Memo',
    tags: ['项目', '任务', '协作'],
    installed: false
  }
]);

const iconMap = {
  ShoppingCart: 'ShoppingCart',
  Edit: 'Edit',
  Money: 'Money',
  User: 'User',
  Memo: 'Memo',
  OfficeBuilding: 'OfficeBuilding',
  DataAnalysis: 'DataAnalysis',
  ChatDotRound: 'ChatDotRound',
  Management: 'Management',
  Files: 'Files'
};

const filteredScenes = computed(() => {
  if (!searchKeyword.value) return scenes.value;
  const kw = searchKeyword.value.toLowerCase();
  return scenes.value.filter(scene =>
    scene.name.toLowerCase().includes(kw) ||
    scene.description.toLowerCase().includes(kw) ||
    scene.tags.some(tag => tag.toLowerCase().includes(kw))
  );
});

const installScene = (scene) => {
  if (scene.installed) {
    ElMessage.info('场景已安装');
    return;
  }
  // 实际项目中调用 API 安装场景
  ElMessage.success(`正在安装“${scene.name}”场景...`);
  scene.installed = true;
};

onMounted(() => {
  // 可加载已安装场景列表
});
</script>

<style scoped>
.marketplace {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header .title {
  font-size: 16px;
  font-weight: 500;
}
.scene-card {
  margin-bottom: 20px;
  cursor: pointer;
  transition: transform 0.2s;
}
.scene-card:hover {
  transform: translateY(-4px);
}
.scene-icon {
  text-align: center;
  margin-bottom: 16px;
  color: #3b82f6;
}
.scene-name {
  font-size: 16px;
  font-weight: 500;
  text-align: center;
  margin-bottom: 8px;
}
.scene-desc {
  font-size: 13px;
  color: #6b7280;
  text-align: center;
  margin-bottom: 12px;
  min-height: 40px;
}
.scene-tags {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.scene-footer {
  text-align: center;
}
</style>