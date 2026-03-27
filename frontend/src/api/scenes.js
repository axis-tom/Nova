// export function getInstalledScenes() {
//   return Promise.resolve([
//     { id: 'ecommerce', name: '电商运营助手' },
//     { id: 'content', name: '自媒体内容管家' },
//     { id: 'finance', name: '财务管理小助手' },
//     { id: 'crm', name: '客户关系维护' }
//   ]);
// }

import client from './client';

// 获取已安装场景列表
export function getInstalledScenes() {
  return client.get('/scenes');
}