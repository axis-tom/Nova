import client from './client';

// 获取当前用户的所有项目
export function getProjects() {
  return client.get('/projects');
}

// 创建项目
export function createProject(data) {
  return client.post('/projects', data);
}

// 更新项目
export function updateProject(id, data) {
  return client.put(`/projects/${id}`, data);
}

// 删除项目
export function deleteProject(id) {
  return client.delete(`/projects/${id}`);
}