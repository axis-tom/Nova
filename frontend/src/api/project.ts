import client from './client';

interface Project {
  id: string | number;
  name: string;
  description?: string;
  [key: string]: unknown;
}

// 获取当前用户的所有项目
export function getProjects(): Promise<{ projects: Project[] }> {
  return client.get('/projects');
}

// 创建项目
export function createProject(data: Partial<Project>): Promise<{ project: Project }> {
  return client.post('/projects', data);
}

// 更新项目
export function updateProject(id: string | number, data: Partial<Project>): Promise<{ project: Project }> {
  return client.put(`/projects/${id}`, data);
}

// 删除项目
export function deleteProject(id: string | number): Promise<unknown> {
  return client.delete(`/projects/${id}`);
}
