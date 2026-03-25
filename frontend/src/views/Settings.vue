<template>
  <div class="settings-page">
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="个人资料" name="profile">
        <ProfileForm
          :profile="profile"
          :loading="profileLoading"
          @update="handleUpdateProfile"
          @change-email="handleChangeEmail"
        />
      </el-tab-pane>
      <el-tab-pane label="数据源" name="dataSources">
        <DataSourceConfig
          :data-sources="dataSources"
          :loading="dataSourceLoading"
          @add="handleAddDataSource"
          @update="handleUpdateDataSource"
          @delete="handleDeleteDataSource"
          @test="handleTestDataSource"
        />
      </el-tab-pane>
      <el-tab-pane label="通知偏好" name="notifications">
        <el-card>
          <el-form :model="notifyForm" label-width="120px">
            <el-form-item label="邮件通知">
              <el-switch v-model="notifyForm.email" />
            </el-form-item>
            <el-form-item label="简报推送">
              <el-switch v-model="notifyForm.briefing" />
            </el-form-item>
            <el-form-item label="风险预警">
              <el-switch v-model="notifyForm.risk" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveNotifications">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import ProfileForm from '@/components/settings/ProfileForm.vue';
import DataSourceConfig from '@/components/settings/DataSourceConfig.vue';
import { useUserStore } from '@/stores/user';
import { useDataSourceStore } from '@/stores/dataSources';
import { getNotificationPreferences, updateNotificationPreferences } from '@/api/settings';

const userStore = useUserStore();
const dataSourceStore = useDataSourceStore();

const activeTab = ref('profile');
const profile = ref({});
const profileLoading = ref(false);
const dataSources = ref([]);
const dataSourceLoading = ref(false);

// 通知偏好
const notifyForm = reactive({
  email: false,
  briefing: false,
  risk: false
});

const loadProfile = async () => {
  profileLoading.value = true;
  try {
    await userStore.fetchProfile();
    profile.value = userStore.profile;
  } finally {
    profileLoading.value = false;
  }
};

const handleUpdateProfile = async (data) => {
  profileLoading.value = true;
  try {
    await userStore.updateProfileData(data);
    ElMessage.success('个人资料已更新');
  } finally {
    profileLoading.value = false;
  }
};

const handleChangeEmail = async (newEmail) => {
  try {
    // 调用 API 发送验证邮件等
    ElMessage.info(`邮箱修改请求已发送到 ${newEmail}，请查收验证邮件`);
  } catch (err) {
    ElMessage.error('修改失败');
  }
};

const loadDataSources = async () => {
  dataSourceLoading.value = true;
  try {
    await dataSourceStore.fetchAll();
    dataSources.value = dataSourceStore.sources;
  } finally {
    dataSourceLoading.value = false;
  }
};

const handleAddDataSource = async (data) => {
  await dataSourceStore.add(data);
  loadDataSources();
};

const handleUpdateDataSource = async ({ id, ...data }) => {
  await dataSourceStore.update(id, data);
  loadDataSources();
};

const handleDeleteDataSource = async (id) => {
  await dataSourceStore.remove(id);
  loadDataSources();
};

const handleTestDataSource = async (source) => {
  try {
    await dataSourceStore.test(source.config);
    ElMessage.success('连接成功');
  } catch (err) {
    ElMessage.error('连接失败：' + err.message);
  }
};

const loadNotifications = async () => {
  try {
    const res = await getNotificationPreferences();
    notifyForm.email = res.notifications.email;
    notifyForm.briefing = res.notifications.briefing;
    notifyForm.risk = res.notifications.risk;
  } catch (err) {
    console.error('加载通知偏好失败', err);
  }
};

const saveNotifications = async () => {
  try {
    await updateNotificationPreferences(notifyForm);
    ElMessage.success('保存成功');
  } catch (err) {
    ElMessage.error('保存失败');
  }
};

onMounted(() => {
  loadProfile();
  loadDataSources();
  loadNotifications();
});
</script>

<style scoped>
.settings-page {
  padding: 20px;
}
</style>