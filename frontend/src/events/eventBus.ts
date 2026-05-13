type EventCallback = (payload: unknown) => void

class EventBus {
  private listeners: Map<string, Set<EventCallback>> = new Map()

  on(event: string, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    this.listeners.get(event)!.add(callback)
    return () => this.off(event, callback)
  }

  emit(event: string, payload: unknown): void {
    const callbacks = this.listeners.get(event)
    if (!callbacks) return
    callbacks.forEach((cb) => {
      try {
        cb(payload)
      } catch (error) {
        console.error(`Error in event listener for "${event}":`, error)
      }
    })
  }

  off(event: string, callback?: EventCallback): void {
    const callbacks = this.listeners.get(event)
    if (!callbacks) return
    if (callback) {
      callbacks.delete(callback)
      if (callbacks.size === 0) this.listeners.delete(event)
    } else {
      this.listeners.delete(event)
    }
  }

  hasListeners(event: string): boolean {
    return this.listeners.has(event) && this.listeners.get(event)!.size > 0
  }

  listenerCount(event: string): number {
    return this.listeners.get(event)?.size ?? 0
  }

  clear(): void {
    this.listeners.clear()
  }
}

let instance: EventBus | null = null

export function getEventBus(): EventBus {
  if (!instance) instance = new EventBus()
  return instance
}

export function resetEventBus(): void {
  instance?.clear()
  instance = null
}

export default getEventBus()