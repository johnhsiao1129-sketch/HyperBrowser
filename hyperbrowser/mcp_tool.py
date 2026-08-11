"""
HyperBrowser MCP 工具接口
兼容 MCP（Model Context Protocol）的工具接口
"""

from typing import Dict, Any

from .agent import HyperBrowserAgent


class HyperBrowserMCPTool:
    """
    兼容 MCP 的工具接口
    
    可以直接集成到 OpenClaw 或 OpenCode 的 MCP 服务器中，
    替代原有的 agent-browser 工具。
    """

    TOOL_NAME = "hyperbrowser_browser"
    TOOL_DESCRIPTION = """
A high-performance browser automation tool with anti-detection capabilities.
Supports batch execution of multiple actions in a single call, significantly
reducing LLM round-trips and token consumption.

Features:
- Batch execution: send multiple actions in one call
- Zero-state calls: operation results returned automatically
- Stealth mode: bypasses Cloudflare, DataDome, and other bot detection
- Lightweight snapshots: only interactive elements, 90% token reduction
"""

    def __init__(self, agent: HyperBrowserAgent):
        self.agent = agent

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用"""
        command = params.get("command", "execute")

        try:
            if command == "navigate":
                url = params.get("url")
                if not url:
                    return {"success": False, "error": "URL is required"}
                result = await self.agent.navigate(url)

            elif command == "execute":
                actions = params.get("actions", [])
                result = await self.agent.execute_actions(actions)

            elif command == "snapshot":
                snapshot = await self.agent.get_snapshot()
                return {
                    "success": True,
                    "snapshot": {
                        "url": snapshot.url,
                        "title": snapshot.title,
                        "interactive_elements": snapshot.interactive_elements,
                        "visible_text": snapshot.visible_text_summary,
                    },
                }

            elif command == "plan_and_execute":
                task = params.get("task")
                if not task:
                    return {"success": False, "error": "Task is required"}
                result = await self.agent.execute_with_llm_planning(task)

            else:
                return {"success": False, "error": f"Unknown command: {command}"}

            return {
                "success": result.success,
                "completed_actions": result.completed_actions,
                "failed_action": result.failed_action,
                "error_message": result.error_message,
                "execution_time_ms": result.execution_time_ms,
                "final_url": result.final_snapshot.url if result.final_snapshot else None,
                "snapshot": {
                    "url": result.final_snapshot.url if result.final_snapshot else None,
                    "interactive_elements": result.final_snapshot.interactive_elements if result.final_snapshot else [],
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_tool_schema(self) -> Dict[str, Any]:
        """返回 MCP 工具的 JSON Schema"""
        return {
            "name": self.TOOL_NAME,
            "description": self.TOOL_DESCRIPTION,
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["navigate", "execute", "snapshot", "plan_and_execute"],
                        "description": "The command to execute",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to (for navigate command)",
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "locator": {"type": "object"},
                                "value": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                        "description": "List of actions to execute (for execute command)",
                    },
                    "task": {
                        "type": "string",
                        "description": "Natural language task description (for plan_and_execute command)",
                    },
                },
                "required": ["command"],
            },
        }

