"""
Session Store — 按 conversation_id 维护 State 的内存级会话存储

设计要点：
- 在同一会话内的多次 call_agent 之间共享 State，让 Nova 原始的流水线 Agent
  能正常串起来（product_collector → collected_products → opportunity_judge 读取）
- TTL 懒回收：访问时顺手清理过期会话，避免后台线程
- MAX_SESSIONS 上限 + LRU 兜底，防止内存爆炸
- 进程内单例 session_store，跨请求保留
"""

import threading
import time
import logging
from typing import Dict, Optional, Tuple

from backend.common.core.state import State
from backend.core.memory.durable import get_durable_session

logger = logging.getLogger(__name__)


class SessionStore:
    """
    按 conversation_id 维护 State 的会话存储

    - get_or_create(conv_id) 取出（或新建）该会话的 State
    - 调用即视为 touch，会刷新 last_access 时间戳
    - TTL 过期 + 容量上限触发懒回收
    """

    TTL_SECONDS = 3600           # 1 小时无访问则过期
    MAX_SESSIONS = 1000          # 容量上限，超过按 LRU 淘汰

    def __init__(self):
        self._sessions: Dict[str, Tuple[State, float]] = {}
        self._lock = threading.RLock()

    def get_or_create(self, conv_id: str) -> State:
        """
        取出指定会话的 State，没有就新建。同时刷新 last_access 时间。
        每次访问触发一次懒回收。

        Phase 3 升级：3 级回退
        1. 内存缓存命中 → 直接返回
        2. 内存未命中 → 查 SQLite，反序列化到内存
        3. SQLite 也没有 → 新建 State
        """
        with self._lock:
            self._evict_expired()

            # Level 1: 内存缓存
            entry = self._sessions.get(conv_id)
            now = time.time()
            if entry is not None:
                state, _ = entry
                self._sessions[conv_id] = (state, now)
                logger.debug(f"[SessionStore] Memory hit: {conv_id}")
                return state

            # Level 2: SQLite 持久化层
            try:
                durable = get_durable_session()
                state_data = durable.load_state(conv_id)
                if state_data is not None:
                    state = State()
                    state.data = state_data.get("data", {})
                    state.events = state_data.get("events", [])
                    state.meta = state_data.get("meta", {"trace_id": None, "step": 0})
                    state.set_meta("conversation_id", conv_id)
                    self._sessions[conv_id] = (state, now)
                    logger.info(f"[SessionStore] SQLite hit: {conv_id}")
                    return state
            except Exception as e:
                logger.warning(f"[SessionStore] SQLite load failed for {conv_id}: {e}")

            # Level 3: 新建会话
            state = State()
            state.set_meta("conversation_id", conv_id)
            self._sessions[conv_id] = (state, now)

            # 容量兜底：超过上限按 last_access 升序淘汰最旧的
            if len(self._sessions) > self.MAX_SESSIONS:
                self._evict_lru(target_size=self.MAX_SESSIONS)

            logger.info(f"[SessionStore] Created new session: {conv_id} (total={len(self._sessions)})")
            return state

    def touch(self, conv_id: str) -> None:
        """显式刷新 last_access 时间戳（一般 get_or_create 已经做过）"""
        with self._lock:
            entry = self._sessions.get(conv_id)
            if entry is not None:
                state, _ = entry
                self._sessions[conv_id] = (state, time.time())

    def save(self, conv_id: str) -> None:
        """
        将指定会话的 State 持久化到 SQLite（Phase 3 新增）
        在 Agent 执行完毕后调用，确保 State 写入持久化层
        """
        with self._lock:
            entry = self._sessions.get(conv_id)
            if entry is None:
                logger.warning(f"[SessionStore] Cannot save non-existent session: {conv_id}")
                return

            state, _ = entry
            try:
                durable = get_durable_session()
                state_data = {
                    "data": state.data,
                    "events": state.events,
                    "meta": state.meta,
                }
                durable.save_state(conv_id, state_data)
                logger.info(f"[SessionStore] Saved session to SQLite: {conv_id}")
            except Exception as e:
                logger.error(f"[SessionStore] Failed to save session {conv_id}: {e}")

    def reset(self, conv_id: str) -> None:
        """清空指定会话的 State（保留 conv_id，重置 data/events）"""
        with self._lock:
            self._sessions.pop(conv_id, None)

    def size(self) -> int:
        with self._lock:
            return len(self._sessions)

    def snapshot_keys(self, conv_id: str) -> Optional[list]:
        """调试用：返回 State.data 的 keys"""
        with self._lock:
            entry = self._sessions.get(conv_id)
            if entry is None:
                return None
            return list(entry[0].data.keys())

    def _evict_expired(self) -> None:
        """懒回收：删除所有 last_access 超过 TTL 的会话"""
        now = time.time()
        expired = [cid for cid, (_, ts) in self._sessions.items()
                   if now - ts > self.TTL_SECONDS]
        for cid in expired:
            del self._sessions[cid]
        if expired:
            logger.info(f"[SessionStore] Evicted {len(expired)} expired sessions")

    def _evict_lru(self, target_size: int) -> None:
        """按 last_access 升序淘汰直到大小达到 target_size"""
        items = sorted(self._sessions.items(), key=lambda kv: kv[1][1])
        for cid, _ in items[: len(self._sessions) - target_size]:
            del self._sessions[cid]


# 模块级单例
session_store = SessionStore()
