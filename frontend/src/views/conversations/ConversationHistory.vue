<template>
  <div class="conversation-history">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">对话历史</span>
          <el-button type="primary" :icon="ChatLineSquare" @click="startNewConversation">
            新对话
          </el-button>
        </div>
      </template>

      <el-table :data="conversations" v-loading="loading" stripe>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="lastMessage" label="最后消息" min-width="300" show-overflow-tooltip />
        <el-table-column prop="updatedAt" label="更新时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.updatedAt, 'YYYY-MM-DD HH:mm') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openConversation(row)">打开</el-button>
            <el-button link type="danger" @click="deleteConversation(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchConversations"
        @current-change="fetchConversations"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ChatLineSquare } from '@element-plus/icons-vue';
import { formatDate } from '@/utils/format';
import { getConversations, deleteConversation as apiDeleteConversation } from '@/api/conversation';

const router = useRouter();
const conversations = ref([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const loading = ref(false);

const fetchConversations = async () => {
  loading.value = true;
  try {
    const res = await getConversations({ page: currentPage.value, limit: pageSize.value });
    conversations.value = res.conversations;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
};

const startNewConversation = () => {
  router.push('/conversations/new');
};

const openConversation = (conv) => {
  router.push(`/conversations/${conv.id}`);
};

const deleteConversation = async (conv) => {
  try {
    await ElMessageBox.confirm(`确定要删除对话“${conv.title}”吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    await apiDeleteConversation(conv.id);
    ElMessage.success('删除成功');
    fetchConversations();
  } catch {
    // 取消
  }
};

onMounted(() => {
  fetchConversations();
});
</script>

<style scoped>
.conversation-history {
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
</style>