import client from './client';

// 获取已安装场景列表
export function getInstalledScenes(): Promise<Array<{ id: string; name: string }>> {
  return client.get('/scenes');
}
