/**
 * WebSocket 管理器（单例模式）
 * 用于处理实时对话消息推送
 */
class WebSocketManager {
  constructor() {
    this.socket = null;
    this.url = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.listeners = {
      open: [],
      message: [],
      close: [],
      error: [],
    };
    this.isConnecting = false;
  }

  /**
   * 连接 WebSocket
   * @param {string} url - WebSocket 地址
   * @param {string} token - JWT token（可选，通常通过 query 或 headers 传递，但浏览器 WebSocket 不支持自定义 headers，需拼接到 URL）
   */
  connect(url, token = null) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }
    if (this.isConnecting) return;

    this.url = url;
    if (token) {
      // 将 token 作为查询参数传递（需后端支持）
      const separator = url.includes('?') ? '&' : '?';
      this.url = `${url}${separator}token=${token}`;
    }

    this.isConnecting = true;
    this.socket = new WebSocket(this.url);

    this.socket.onopen = (event) => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.isConnecting = false;
      this._emit('open', event);
    };

    this.socket.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (e) {
        data = event.data;
      }
      this._emit('message', data);
    };

    this.socket.onclose = (event) => {
      console.log('WebSocket closed', event);
      this.isConnecting = false;
      this._emit('close', event);
      // 自动重连
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          console.log(`Reconnecting... attempt ${this.reconnectAttempts + 1}`);
          this.reconnectAttempts++;
          this.connect(this.url);
        }, this.reconnectDelay);
      }
    };

    this.socket.onerror = (error) => {
      console.error('WebSocket error', error);
      this._emit('error', error);
    };
  }

  /**
   * 发送消息
   * @param {object|string} data
   */
  send(data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      this.socket.send(message);
    } else {
      console.warn('WebSocket not open, cannot send');
    }
  }

  /**
   * 关闭连接
   */
  close() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  /**
   * 添加事件监听
   * @param {string} event - 'open', 'message', 'close', 'error'
   * @param {function} callback
   */
  on(event, callback) {
    if (!this.listeners[event]) return;
    this.listeners[event].push(callback);
  }

  /**
   * 移除事件监听
   * @param {string} event
   * @param {function} callback
   */
  off(event, callback) {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
  }

  _emit(event, data) {
    if (!this.listeners[event]) return;
    this.listeners[event].forEach(cb => cb(data));
  }
}

// 导出单例
export const wsManager = new WebSocketManager();