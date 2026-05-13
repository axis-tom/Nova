/**
 * 校验邮箱格式
 * @param email - 邮箱地址
 */
export function isEmail(email: string): boolean {
  const re: RegExp = /^[^\s@]+@([^\s@]+\.)+[^\s@]+$/;
  return re.test(email);
}

/**
 * 校验手机号（中国大陆）
 * @param phone - 手机号
 */
export function isPhone(phone: string): boolean {
  const re: RegExp = /^1[3-9]\d{9}$/;
  return re.test(phone);
}

/**
 * 校验密码强度（至少6位，包含字母和数字）
 * @param password - 密码
 */
export function isStrongPassword(password: string): boolean {
  if (!password || password.length < 6) return false;
  const hasLetter: boolean = /[a-zA-Z]/.test(password);
  const hasNumber: boolean = /\d/.test(password);
  return hasLetter && hasNumber;
}

/**
 * 校验非空
 * @param value - 任意值
 */
export function isNotEmpty(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value as object).length > 0;
  return true;
}

/**
 * 校验 URL 格式
 * @param url - URL 字符串
 */
export function isUrl(url: string): boolean {
  const re: RegExp = /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/;
  return re.test(url);
}