"""
Agent Orchestrator MVP — CLI 入口
启动命令行交互式对话
"""

import asyncio
import os
import sys

# 确保 Nova backend 在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nova_agent_system.orchestrator import run_orchestrator
from nova_agent_system.memory_scheduler import start_scheduler, stop_scheduler


def print_banner():
    """打印启动横幅"""
    banner = r"""
╔══════════════════════════════════════╗
║   Nova Agent Orchestrator MVP       ║
║   LangGraph + ReAct + Nova Agents   ║
╚══════════════════════════════════════╝
"""
    print(banner)
    print("输入你的问题，例如：")
    print("  - 帮我分析蓝牙耳机品类 Top 10 商品")
    print("  - 搜索最新的 Amazon 蓝牙耳机市场趋势")
    print("  - 对比以下产品的优劣势")
    print("  - 退出: quit / exit / q")
    print()


async def main():
    """CLI 主循环"""
    # 启动后台记忆调度器（每 1 小时整合，每 24 小时遗忘）
    try:
        scheduler = start_scheduler(consolidate_interval=3600, forget_interval=86400)
        print("📀 记忆调度器已启动")
    except Exception as e:
        print(f"⚠️ 记忆调度器启动失败: {e}")

    print_banner()

    while True:
        try:
            user_input = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        print("\n🤖 思考中...\n")

        try:
            response = await run_orchestrator(user_input)
            print(f"\n{response}")
        except Exception as e:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        stop_scheduler()
