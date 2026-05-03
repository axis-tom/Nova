/**
 * 格式化日期
 * @param date - 可转换为 Date 的值
 * @param format - 格式，如 'YYYY-MM-DD HH:mm:ss'
 */
export function formatDate(date: Date | string | number | null | undefined, format: string = 'YYYY-MM-DD HH:mm:ss'): string {
  if (!date) return '';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '';

  const year: string = String(d.getFullYear());
  const month: string = String(d.getMonth() + 1).padStart(2, '0');
  const day: string = String(d.getDate()).padStart(2, '0');
  const hours: string = String(d.getHours()).padStart(2, '0');
  const minutes: string = String(d.getMinutes()).padStart(2, '0');
  const seconds: string = String(d.getSeconds()).padStart(2, '0');

  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds);
}

/**
 * 相对时间（如"刚刚"、"5分钟前"）
 * @param date - 可转换为 Date 的值
 */
export function timeAgo(date: Date | string | number): string {
  const now: Date = new Date();
  const past: Date = new Date(date);
  const diff: number = (now.getTime() - past.getTime()) / 1000; // 秒

  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)}天前`;
  if (diff < 31536000) return `${Math.floor(diff / 2592000)}个月前`;
  return `${Math.floor(diff / 31536000)}年前`;
}

/**
 * 截断文本
 * @param text - 原始文本
 * @param length - 最大长度
 * @param suffix - 截断后缀
 */
export function truncate(text: string | null | undefined, length: number = 50, suffix: string = '...'): string {
  if (!text) return '';
  if (text.length <= length) return text;
  return text.substring(0, length) + suffix;
}

/**
 * 格式化数字（千分位）
 * @param num - 数字
 */
export function formatNumber(num: number | null | undefined): string {
  if (num === undefined || num === null) return '';
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * 格式化文件大小
 * @param bytes - 字节数
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k: number = 1024;
  const sizes: string[] = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i: number = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 别名导出，用于兼容组件中的导入
export const formatRelativeTime = timeAgo;