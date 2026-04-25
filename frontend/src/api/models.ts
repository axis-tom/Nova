import client from './client';

// 获取可用的AI模型列表
export function getLocalModels(): Promise<Array<{ id: string; name: string }>> {
  return client.get('/models/available');
}
