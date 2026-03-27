/**
 * 格式化日期
 * @param {Date|string|number} date - 可转换为 Date 的值
 * @param {string} format - 格式，如 'YYYY-MM-DD HH:mm:ss'
 * @returns {string}
 */
export function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return '';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '';

  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const seconds = String(d.getSeconds()).padStart(2, '0');

  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds);
}

/**
 * 相对时间（如“刚刚”、“5分钟前”）
 * @param {Date|string|number} date
 * @returns {string}
 */
export function timeAgo(date) {
  const now = new Date();
  const past = new Date(date);
  const diff = (now - past) / 1000; // 秒

  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)}天前`;
  if (diff < 31536000) return `${Math.floor(diff / 2592000)}个月前`;
  return `${Math.floor(diff / 31536000)}年前`;
}

/**
 * 截断文本
 * @param {string} text
 * @param {number} length
 * @param {string} suffix
 * @returns {string}
 */
export function truncate(text, length = 50, suffix = '...') {
  if (!text) return '';
  if (text.length <= length) return text;
  return text.substring(0, length) + suffix;
}

/**
 * 格式化数字（千分位）
 * @param {number} num
 * @returns {string}
 */
export function formatNumber(num) {
  if (num === undefined || num === null) return '';
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * 格式化文件大小
 * @param {number} bytes
 * @returns {string}
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 别名导出，用于兼容组件中的导入
export const formatRelativeTime = timeAgo;