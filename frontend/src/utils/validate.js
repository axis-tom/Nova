/**
 * 校验邮箱格式
 * @param {string} email
 * @returns {boolean}
 */
export function isEmail(email) {
  const re = /^[^\s@]+@([^\s@]+\.)+[^\s@]+$/;
  return re.test(email);
}

/**
 * 校验手机号（中国大陆）
 * @param {string} phone
 * @returns {boolean}
 */
export function isPhone(phone) {
  const re = /^1[3-9]\d{9}$/;
  return re.test(phone);
}

/**
 * 校验密码强度（至少6位，包含字母和数字）
 * @param {string} password
 * @returns {boolean}
 */
export function isStrongPassword(password) {
  if (!password || password.length < 6) return false;
  const hasLetter = /[a-zA-Z]/.test(password);
  const hasNumber = /\d/.test(password);
  return hasLetter && hasNumber;
}

/**
 * 校验非空
 * @param {any} value
 * @returns {boolean}
 */
export function isNotEmpty(value) {
  if (value === undefined || value === null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
}

/**
 * 校验 URL 格式
 * @param {string} url
 * @returns {boolean}
 */
export function isUrl(url) {
  const re = /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/;
  return re.test(url);
}