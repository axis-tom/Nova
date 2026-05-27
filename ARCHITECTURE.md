# Nova 架构地图

## 13 层 AI Agent 框架 → 代码位置映射

```
Layer                         → 代码位置
───────────────────────────      ────────────────────────────────────────
1  Interface Layer (接口层)      api/routes/ + api/deps.py
2  Orchestration Layer (编排层)   core/orchestrator.py
3  Cognitive Layer (认知层)       core/orchestrator.py + core/llm/ + core/agent.py
4  Tool Layer (工具层)            core/tools/ + core/agent.py:_run_analysis_loop
5  Memory System (记忆系统)       core/memory/
6  Knowledge Layer (知识层)       core/memory/vector_store.py (ChromaDB RAG)
7  Execution Runtime (执行环境)   N/A (不需要)
8  Data Infrastructure (数据层)   data/ + connectors/ + infrastructure/
9  Observability (可观测性)       core/tracking/ (Phase 2: + tracer.py + prompt_logger.py)
10 Governance & Safety (治理安全) N/A (Phase 2: core/guardrails/)
11 Evaluation (评估系统)          N/A (Phase 3 按需)
12 Economic Layer (经济层)        core/llm/config.py (成本追踪) + business/ (budget 调度)
13 Learning Layer (学习层)        core/memory/scheduler.py (consolidate/forget)
```

## 目录职责

```
backend/
├── api/                          # Layer 1: HTTP 接口
│   ├── deps.py                   #   公共依赖 (get_db, get_current_user)
│   └── routes/                   #   REST + SSE 端点
│
├── core/                         # AI Agent 引擎 (Layer 2-6, 9, 13)
│   ├── orchestrator.py           #   LangGraph ReAct 循环
│   ├── agent.py                  #   Agent 抽象基类 + LLM 分析循环
│   ├── agent_wrapper.py          #   Agent 注册表 + 懒加载 + 调用包装
│   ├── llm/                      #   Layer 3: LLM 路由 + 成本
│   ├── tools/                    #   Layer 4: 工具集 (web_search, db_query, call_agent)
│   ├── memory/                   #   Layer 5+6: ChromaDB + SQLite + 调度
│   ├── tracking/                 #   Layer 9: 分析树追踪
│   ├── cache/                    #   缓存层 (Keepa)
│   └── protocols/                #   接口定义 (StateBackend, MessageBus, AgentRegistry)
│
├── business/                     # Layer 2 业务 Agent
│   └── ecommerce/                #   亚马逊电商
│       ├── amazon_monitor/       #     市场监控调度器
│       ├── product_selection/    #     选品分析
│       └── ...                   #     ETL, scoring, budget
│
├── connectors/                   # Layer 8: 外部数据源适配器
│   ├── amazon/                   #   Amazon PAAPI 5.0
│   ├── email/                    #   IMAP 邮件采集
│   ├── outbound/                 #   飞书/Notion/Todoist 推送
│   ├── social/                   #   微博/小红书
│   ├── crawler_pool.py           #   爬虫池
│   └── ...
│
├── data/                         # Layer 8: 数据访问层
│   ├── database.py               #   SQLAlchemy engine + session
│   ├── models/                   #   ORM 模型
│   └── repositories/             #   Repository 模式
│
├── infrastructure/               # Layer 8: 基础设施
│   ├── message_bus.py            #   事件总线
│   ├── audit_logger.py           #   审计日志
│   └── scheduler_manager.py      #   定时任务管理器
│
├── common/                       # 共享数据模型
│   ├── core/
│   │   ├── state.py              #   State 对象
│   │   └── analysis_trace.py     #   分析树数据结构
│   └── context.py
│
└── config/                       # 配置
    ├── config.py
    ├── data_source_providers.py
    └── prompts.py (Phase 2)
```

## 关键流程

```
用户提问
  │
  ▼
api/routes/agent_chat.py    (SSE 流式 / JSON)
  │
  ▼
core/orchestrator.py        (LangGraph ReAct 循环)
  ├── call_model()           → LLM (core/llm/config.py)
  ├── execute_tools()        → web_search / memory / db_query / call_nova_agent
  │                              └── core/agent_wrapper.py → business/agents/
  └── should_continue()      → 判断是否结束
  │
  ▼
core/memory/vector_store.py (ChromaDB RAG 检索 + 记忆)
core/memory/durable.py      (SQLite 持久化)
  │
  ▼
core/tracking/analysis_tree.py (追踪 + 前端 SSE 推送)
  │
  ▼
回复用户
```

## 设计原则

1. **目录 = 职责**，不按框架层切分文件
2. **父目录不引用子目录**
3. **nova_agent_system/ 和 foundation/ 已废弃**（Phase 1 搬迁完成），所有代码在 `backend/` 下
4. `connectors/` 只做数据格式转换和传输，不包含业务逻辑
5. `business/` 只包含业务 Agent，不直接调用外部 API（通过 connectors/ 代理）