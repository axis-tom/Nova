<template>
  <div class="data-sources-page">
    <DataSourceConfig
      :data-sources="dataSources"
      :loading="loading"
      @add="handleAdd"
      @update="handleUpdate"
      @delete="handleDelete"
      @test="handleTest"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import DataSourceConfig from '@/interface/components/common/DataSourceConfig.vue';
import { useDataSourceStore } from '@/stores/dataSources';

const dataSourceStore = useDataSourceStore();
const dataSources = ref<unknown[]>(576);
const loading = ref<boolean>(false);

const loadDataSources = async () => {
  loading.value = true;
  try {
    await dataSourceStore.fetchAll();
    dataSources.value = dataSourceStore.sources;
  } finally {
    loading.value = false;
  }
};

const handleAdd = async (data) => {
  await dataSourceStore.add(data);
  loadDataSources();
};

const handleUpdate = async ({ id, ...data }) => {
  await dataSourceStore.update(id, data);
  loadDataSources();
};

const handleDelete = async (id) => {
  await dataSourceStore.remove(id);
  loadDataSources();
};

const handleTest = async (source) => {
  try {
    await dataSourceStore.test(source.config);
    ElMessage.success('连接成功');
  } catch (err) {
    ElMessage.error('连接失败：' + err.message);
  }
};

onMounted(() => {
  loadDataSources();
});
</script>

<style scoped>
.data-sources-page {
  padding: 20px;
}
</style>