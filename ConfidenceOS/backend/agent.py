"""
agent.py — builds and returns the compiled LangGraph agent.
Imported once at startup by main.py.
"""

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

import config
from tools import ALL_TOOLS


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ── LLM ───────────────────────────────────────────────────────────────────────

llm = ChatOllama(
    base_url=config.OLLAMA_BASE_URL,
    model=config.OLLAMA_MODEL,
    temperature=0,           # deterministic tool calling
)
llm_with_tools = llm.bind_tools(ALL_TOOLS)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def agent_node(state: AgentState) -> AgentState:
    """Call the LLM with the current message history."""
    messages = [SystemMessage(content=config.SYSTEM_PROMPT), *state["messages"]]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """If the LLM wants to call a tool, go to 'tools'; otherwise finish."""
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph():
    tool_node = ToolNode(ALL_TOOLS)

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)

    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")

    return g.compile()


# Compile once; main.py imports this object
graph = build_graph()
