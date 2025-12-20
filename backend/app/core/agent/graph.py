from langgraph.graph import StateGraph, END
from app.core.agent.state import AgentState
from app.core.agent.nodes import (
    planning_node,
    search_node,
    analyze_node,
    report_node
)


def create_agent_graph():
    """에이전트 워크플로우 생성"""

    # 그래프 생성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("planning", planning_node)
    workflow.add_node("search", search_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("report", report_node)

    # 엣지 연결 (순차 실행)
    workflow.set_entry_point("planning")
    workflow.add_edge("planning", "search")
    workflow.add_edge("search", "analyze")
    workflow.add_edge("analyze", "report")
    workflow.add_edge("report", END)

    # 컴파일
    return workflow.compile()

agent = create_agent_graph()