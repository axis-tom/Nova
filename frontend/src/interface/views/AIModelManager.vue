<template>
  <div class="model-management">
    <el-card>
      <template #header>
        <div class="header-actions">
          <span>AI 模型管理</span>
          <div>
            <el-button type="primary" @click="showDownloadDialog = true">下载模型</el-button>
            <el-button @click="showNewFolderDialog = true">新建文件夹</el-button>
          </div>
        </div>
      </template>

      <div class="main-layout">
        <!-- 文件夹树 -->
        <div class="folder-tree">
          <el-tree
            :data="folderTree"
            :props="{ label: 'name', children: 'children' }"
            node-key="path"
            highlight-current
            @node-click="handleNodeClick"
          />
        </div>

        <!-- 内容区域 -->
        <div class="content-area">
          <div class="breadcrumb">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '' }" @click="goToRoot">根目录</el-breadcrumb-item>
              <el-breadcrumb-item
                v-for="(part, idx) in pathParts"
                :key="idx"
                @click="navigateToPath(part.fullPath)"
              >
                {{ part.name }}
              </el-breadcrumb-item>
            </el-breadcrumb>
          </div>

          <el-table :data="displayItems" v-loading="modelStore.loading">
            <el-table-column label="名称">
              <template #default="{ row }">
                <div class="item-name">
                  <el-icon v-if="row.isFolder"><Folder /></el-icon>
                  <el-icon v-else><Document /></el-icon>
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="大小" prop="size_mb" width="120">
              <template #default="{ row }">
                <span v-if="!row.isFolder">{{ row.size_mb }} MB</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button
                  v-if="row.isFolder"
                  link
                  type="primary"
                  @click="editFolder(row)"
                >
                  重命名
                </el-button>
                <el-button
                  v-if="row.isFolder"
                  link
                  type="danger"
                  @click="deleteFolder(row)"
                >
                  删除
                </el-button>
                <el-button
                  v-else
                  link
                  type="danger"
                  @click="deleteModel(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-card>

    <!-- 新建文件夹对话框 -->
    <el-dialog v-model="showNewFolderDialog" title="新建文件夹" width="400px">
      <el-input v-model="newFolderName" placeholder="文件夹名称" />
      <template #footer>
        <el-button @click="showNewFolderDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateFolder">确定</el-button>
      </template>
    </el-dialog>

    <!-- 下载模型对话框 -->
    <el-dialog v-model="showDownloadDialog" title="下载模型" width="500px">
      <el-radio-group v-model="selectedModel">
        <el-radio v-for="model in presetModels" :key="model.name" :label="model.name">
          {{ model.name }} - {{ model.size_mb }} MB
        </el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="showDownloadDialog = false">取消</el-button>
        <el-button type="primary" @click="handleDownloadModel">下载</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Folder, Document } from '@element-plus/icons-vue';
import { useModelStore } from '@/state/models';

const modelStore = useModelStore();

const showNewFolderDialog = ref<boolean>(false);
const showDownloadDialog = ref<boolean>(false);
const newFolderName = ref<string>('');
const selectedModel = ref<string>('');

// 预设模型列表（可从后端配置获取）
const presetModels = ref([
  { name: 'qwen2.5-3b-instruct', size_mb: 2100, description: 'Qwen2.5 3B 指令模型' },
  { name: 'llama3-8b-instruct', size_mb: 4400, description: 'Llama3 8B 指令模型' },
]);

const pathParts = computed(() => {
  if (!modelStore.currentPath) return [];
  const parts = modelStore.currentPath.split('/').filter(p => p);
  let accumulated = '';
  return parts.map(part => {
    accumulated = accumulated ? `${accumulated}/${part}` : part;
    return { name: part, fullPath: accumulated };
  });
});

const displayItems = computed(() => {
  const folders = modelStore.folders.map(f => ({ ...f, isFolder: true }));
  const models = modelStore.models.map(m => ({ ...m, isFolder: false }));
  return [...folders, ...models];
});

// 文件夹树构建（简化版，实际应递归获取）
const folderTree = computed(() => {
  // 这里简单返回顶层文件夹，更完整实现需要递归构建
  return modelStore.folders.map(f => ({ name: f.name, path: f.path, children: [] }));
});

const goToRoot = () => modelStore.changeDirectory('');
const navigateToPath = (path) => modelStore.changeDirectory(path);
const handleNodeClick = (node) => modelStore.changeDirectory(node.path);

const handleCreateFolder = async () => {
  if (!newFolderName.value) return;
  await modelStore.createFolder(newFolderName.value);
  showNewFolderDialog.value = false;
  newFolderName.value = '';
  ElMessage.success('文件夹已创建');
};

const editFolder = (row) => {
  ElMessageBox.prompt('请输入新名称', '重命名文件夹', {
    inputValue: row.name,
  }).then(async ({ value }) => {
    if (value && value !== row.name) {
      await modelStore.renameFolder(row.path, value);
      ElMessage.success('重命名成功');
    }
  });
};

const deleteFolder = (row) => {
  ElMessageBox.confirm(`确定删除文件夹 "${row.name}" 吗？其中的模型也会被删除。`, '警告', {
    type: 'warning',
  }).then(async () => {
    await modelStore.deleteFolder(row.path);
    ElMessage.success('删除成功');
  });
};

const deleteModel = (row) => {
  ElMessageBox.confirm(`确定删除模型 "${row.name}" 吗？`, '警告', {
    type: 'warning',
  }).then(async () => {
    await modelStore.deleteModel(row.path);
    ElMessage.success('删除成功');
  });
};

const handleDownloadModel = async () => {
  if (!selectedModel.value) return;
  await modelStore.downloadModel(selectedModel.value);
  showDownloadDialog.value = false;
  ElMessage.success('模型下载已开始，请稍后刷新列表');
};

onMounted(() => {
  modelStore.loadData();
});
</script>

<style scoped>
.model-management {
  padding: 20px;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.main-layout {
  display: flex;
  gap: 20px;
  min-height: 500px;
}
.folder-tree {
  width: 250px;
  border-right: 1px solid #e4e7ed;
  padding-right: 10px;
}
.content-area {
  flex: 1;
}
.breadcrumb {
  margin-bottom: 16px;
}
.item-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>