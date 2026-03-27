// // 模拟获取树形数据
// export function getTreeData() {
//   return Promise.resolve([
//     { id: 1, name: '示例项目', type: 'project', children: [
//       { id: 101, name: '对话示例', type: 'conversation' }
//     ] }
//   ]);
// }

// export function createProjectApi(data) {
//   return Promise.resolve({ id: Date.now(), name: data.name });
// }
// export function updateProjectApi(id, data) {
//   return Promise.resolve({ id, ...data });
// }
// export function deleteProjectApi(id) {
//   return Promise.resolve();
// }
// export function createConversationApi(data) {
//   return Promise.resolve({ id: Date.now(), name: data.name, projectId: data.projectId });
// }
// export function updateConversationApi(id, data) {
//   return Promise.resolve({ id, ...data });
// }
// export function deleteConversationApi(id) {
//   return Promise.resolve();
// }
// export function getConversationMessages(conversationId) {
//   return Promise.resolve({ messages: [] });
// }
// export function sendMessageApi(data) {
//   return Promise.resolve({ reply: '这是模拟回复' });
// }