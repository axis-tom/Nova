/**
 * WebSocket 事件类型
 */
type WsEventName = 'open' | 'message' | 'close' | 'error';

/**
 * WebSocket 事件回调类型
 */
type WsCallback = (data: unknown) => void;

/**
 * WebSocket 管理器（单例模式）
 * 用于处理实时对话消息推送
 */
class WebSocketManager {
  private socket: WebSocket | null = null;
  private url: string | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 3000;
  private listeners: Record<WsEventName, WsCallback[]> = {
    open: [],
    message: [],
    close: [],
    error: [],
  };
  private isConnecting: boolean = false;

  /**
   * 连接 WebSocket
   * @param url - WebSocket 地址
   * @param token - JWT token
   */
  connect(url: string, token: string | null = null): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }
    if (this.isConnecting) return;

    this.url = url;
    if (token) {
      const separator: string = url.includes('?') ? '&' : '?';
      this.url = `${url}${separator}token=${token}`;
    }

    this.isConnecting = true;
    this.socket = new WebSocket(this.url);

    this.socket.onopen = (event: Event): void => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.isConnecting = false;
      this._emit('open', event);
    };

    this.socket.onmessage = (event: MessageEvent): void => {
      let data: unknown;
      try {
        data = JSON.parse(event.data);
      } catch {
        data = event.data;
      }
      this._emit('message', data);
    };

    this.socket.onclose = (event: CloseEvent): void => {
      console.log('WebSocket closed', event);
      this.isConnecting = false;
      this._emit('close', event);
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout((): void => {
          console.log(`Reconnecting... attempt ${this.reconnectAttempts + 1}`);
          this.reconnectAttempts++;
          this.connect(this.url as string);
        }, this.reconnectDelay);
      }
    };

    this.socket.onerror = (error: Event): void => {
      console.error('WebSocket error', error);
      this._emit('error', error);
    };
  }

  /**
   * 发送消息
   * @param data - 消息内容
   */
  send(data: object | string): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message: string = typeof data === 'string' ? data : JSON.stringify(data);
      this.socket.send(message);
    } else {
      console.warn('WebSocket not open, cannot send');
    }
  }

  /**
   * 关闭连接
   */
  close(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  /**
   * 添加事件监听
   * @param event - 'open', 'message', 'close', 'error'
   * @param callback - 回调函数
   */
  on(event: WsEventName, callback: WsCallback): void {
    if (!this.listeners[event]) return;
    this.listeners[event].push(callback);
  }

  /**
   * 移除事件监听
   * @param event - 事件名
   * @param callback - 回调函数
   */
  off(event: WsEventName, callback: WsCallback): void {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter((cb: WsCallback): boolean => cb !== callback);
  }

  private _emit(event: WsEventName, data: unknown): void {
    if (!this.listeners[event]) return;
    this.listeners[event].forEach((cb: WsCallback): void => cb(data));
  }
}

// 导出单例
export const wsManager: WebSocketManager = new WebSocketManager();