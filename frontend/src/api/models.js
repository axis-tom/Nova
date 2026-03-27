// import client from './client';

// export function listFolders(parent = '') {
//   return client.get('/models/folders', { params: { parent } });
// }

// export function createFolder(name, parent = '') {
//   return client.post('/models/folders', { name, parent });
// }

// export function renameFolder(path, newName) {
//   return client.put(`/models/folders/${encodeURIComponent(path)}`, { new_name: newName });
// }

// export function deleteFolder(path) {
//   return client.delete(`/models/folders/${encodeURIComponent(path)}`);
// }

// export function listModels(folder = '') {
//   return client.get('/models/list', { params: { folder } });
// }

// export function downloadModel(modelName, folder = '') {
//   return client.post('/models/download', { model_name: modelName, folder });
// }

// export function deleteModel(path) {
//   return client.delete(`/models/${encodeURIComponent(path)}`);
// }

// // 获取本地可用的 AI 模型（模拟数据，实际应调用后端接口）
// export function getLocalModels() {
//   // 模拟返回数据，实际可调用 /models/available 或类似接口
//   return Promise.resolve([
//     { id: 'qwen2.5-3b', name: 'Qwen2.5 3B' },
//     { id: 'llama3-8b', name: 'Llama3 8B' },
//     { id: 'mistral-7b', name: 'Mistral 7B' }
//   ]);
// }


import client from './client';

// 获取可用的AI模型列表
export function getLocalModels() {
  return client.get('/models/available');
}