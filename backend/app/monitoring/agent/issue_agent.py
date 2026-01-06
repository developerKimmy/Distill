"""IssueAgent - LangGraph 기반 이슈 정보 수집 Agent

ReAct 패턴:
1. ANALYZE: GapAnalyzer로 정보 충분도 평가
2. DECIDE: 다음 도구 선택
3. ACT: 도구 실행, 정보 추가
4. LOOP: 충분할 때까지 반복
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Literal

from langgraph.graph import StateGraph, END

from app.monitoring.agent.state import IssueAgentState, ToolCall
from app.monitoring.agent.tools import AgentToolkit
from app.monitoring.agent.decisions import decide_next_action, should_continue
from app.core.config import settings

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


# ========== 노드 함수들 ==========

async def analyze_node(state: IssueAgentState) -> dict:
    """ANALYZE: 정보 충분도 분석"""
    logger.info(f"[IssueAgent] ANALYZE: {state['issue_name']}")

    toolkit = AgentToolkit()

    # 기사를 dict 형태로 변환
    articles_for_analysis = [
        {"title": a.get("title", ""), "description": a.get("description", "")}
        for a in state["articles"]
    ]

    # Gap 분석
    result = toolkit.analyze_gaps(
        issue_name=state["issue_name"],
        articles=articles_for_analysis
    )

    logger.info(
        f"[IssueAgent] 분석 결과: confidence={result.confidence:.2f}, "
        f"gaps={len(result.gaps)}, claims={len(result.key_claims)}"
    )

    return {
        "confidence": result.confidence,
        "gaps": result.gaps,
        "key_claims": result.key_claims,
        "status": "deciding"
    }


async def decide_node(state: IssueAgentState) -> dict:
    """DECIDE: 다음 액션 결정"""
    logger.info(f"[IssueAgent] DECIDE: iteration={state['iteration']}")

    next_action = decide_next_action(
        issue_name=state["issue_name"],
        articles_count=len(state["articles"]),
        confidence=state["confidence"],
        gaps=state["gaps"],
        actions_taken=state["actions_taken"]
    )

    if next_action:
        logger.info(f"[IssueAgent] 다음 액션: {next_action['tool']} - {next_action['query']}")
    else:
        logger.info(f"[IssueAgent] 액션 없음 → 종료 준비")

    return {
        "next_action": next_action,
        "status": "acting" if next_action else "done"
    }


async def act_node(state: IssueAgentState) -> dict:
    """ACT: 도구 실행"""
    action = state["next_action"]
    if not action:
        return {"status": "done"}

    tool = action["tool"]
    query = action["query"]

    logger.info(f"[IssueAgent] ACT: {tool} - '{query}'")

    toolkit = AgentToolkit()
    new_articles = []
    supplementary = []
    error = None

    try:
        if tool == "tavily":
            # Tavily 결과는 supplementary_data로
            results = await toolkit.search_tavily(query)
            supplementary = results
            logger.info(f"[IssueAgent] Tavily: {len(results)}개 수집")

        elif tool == "naver":
            # Naver 결과는 articles에 병합
            results = await toolkit.search_naver(query)
            existing_urls = {a.get("url", "") for a in state["articles"]}
            new_articles = [r for r in results if r.get("url") not in existing_urls]
            logger.info(f"[IssueAgent] Naver: {len(new_articles)}개 신규")

        elif tool == "google_news":
            results = await toolkit.search_google(query)
            existing_urls = {a.get("url", "") for a in state["articles"]}
            new_articles = [r for r in results if r.get("url") not in existing_urls]
            logger.info(f"[IssueAgent] Google: {len(new_articles)}개 신규")

    except Exception as e:
        error = f"{tool}: {str(e)}"
        logger.error(f"[IssueAgent] 도구 실행 실패: {e}")

    # 액션 기록
    tool_call = ToolCall(
        tool=tool,
        query=query,
        reason=action.get("reason", ""),
        results_count=len(new_articles) + len(supplementary),
        timestamp=datetime.now(KST).isoformat()
    )

    # 결과 반환
    result = {
        "iteration": state["iteration"] + 1,
        "next_action": None,
        "status": "analyzing",
        "actions_taken": [tool_call],
    }

    if new_articles:
        result["articles"] = state["articles"] + new_articles

    if supplementary:
        result["supplementary_data"] = supplementary

    if error:
        result["errors"] = [error]

    return result


async def done_node(state: IssueAgentState) -> dict:
    """DONE: 완료 처리"""
    logger.info(
        f"[IssueAgent] DONE: {state['issue_name']} "
        f"(articles={len(state['articles'])}, confidence={state['confidence']:.2f}, "
        f"iterations={state['iteration']})"
    )
    return {"status": "done"}


# ========== 라우팅 함수 ==========

def route_after_decide(state: IssueAgentState) -> Literal["act", "done"]:
    """decide 후 라우팅: 액션이 있으면 act, 없으면 done"""
    if state["next_action"] is None:
        return "done"

    # 최대 반복 체크
    if state["iteration"] >= state["max_iterations"]:
        return "done"

    return "act"


# ========== 그래프 빌드 ==========

def build_issue_agent_graph() -> StateGraph:
    """IssueAgent 그래프 빌드"""
    graph = StateGraph(IssueAgentState)

    # 노드 추가
    graph.add_node("analyze", analyze_node)
    graph.add_node("decide", decide_node)
    graph.add_node("act", act_node)
    graph.add_node("done", done_node)

    # 엣지 추가
    graph.add_edge("analyze", "decide")
    graph.add_conditional_edges(
        "decide",
        route_after_decide,
        {"act": "act", "done": "done"}
    )
    graph.add_edge("act", "analyze")  # 피드백 루프
    graph.add_edge("done", END)

    # 시작점
    graph.set_entry_point("analyze")

    return graph.compile()


# ========== 메인 클래스 ==========

class IssueAgent:
    """개별 이슈 처리 Agent"""

    def __init__(self, max_iterations: int | None = None):
        self.max_iterations = max_iterations or settings.AGENT_MAX_ITERATIONS
        self.graph = build_issue_agent_graph()

    async def process(
        self,
        issue_id: str,
        issue_name: str,
        initial_articles: list[dict],
        category: str | None = None
    ) -> IssueAgentState:
        """이슈 처리 실행

        Args:
            issue_id: 이슈 ID
            issue_name: 이슈명
            initial_articles: 초기 기사들
            category: 카테고리

        Returns:
            최종 Agent 상태
        """
        initial_state: IssueAgentState = {
            "issue_id": issue_id,
            "issue_name": issue_name,
            "category": category,
            "articles": list(initial_articles),
            "supplementary_data": [],
            "confidence": 0.0,
            "gaps": [],
            "key_claims": [],
            "next_action": None,
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "status": "analyzing",
            "actions_taken": [],
            "errors": [],
        }

        logger.info(
            f"[IssueAgent] 시작: {issue_name} "
            f"(기사 {len(initial_articles)}개, max_iter={self.max_iterations})"
        )

        # 그래프 실행
        final_state = await self.graph.ainvoke(initial_state)

        return final_state


# ========== 헬퍼 함수 ==========

async def run_issue_agents(
    matched_results: list[dict],
    articles: list[dict],
    min_articles: int | None = None
) -> list[IssueAgentState]:
    """여러 이슈에 대해 Agent 실행

    Args:
        matched_results: Match 노드 결과
        articles: 수집된 기사들
        min_articles: 이 미만이면 Agent 실행 (기본: settings.AGENT_MIN_ARTICLES)

    Returns:
        Agent 결과 리스트
    """
    min_articles = min_articles or settings.AGENT_MIN_ARTICLES

    # 이슈별로 그룹화
    issue_data = {}
    for result in matched_results:
        issue_id = result.get("issue_id", "")
        if not issue_id or issue_id == "UNASSIGNED":
            continue

        if issue_id not in issue_data:
            issue_data[issue_id] = {
                "name": result.get("issue_name", ""),
                "articles": []
            }

        idx = result.get("article_idx", -1)
        if 0 <= idx < len(articles):
            issue_data[issue_id]["articles"].append(articles[idx])

    # 기사 수 적은 이슈만 Agent 실행
    agent = IssueAgent()
    results = []

    for issue_id, data in issue_data.items():
        if len(data["articles"]) < min_articles:
            logger.info(
                f"[Agent] {data['name']}: 기사 {len(data['articles'])}개 < {min_articles} → Agent 실행"
            )
            state = await agent.process(
                issue_id=issue_id,
                issue_name=data["name"],
                initial_articles=data["articles"]
            )
            results.append(state)
        else:
            logger.info(
                f"[Agent] {data['name']}: 기사 {len(data['articles'])}개 >= {min_articles} → 스킵"
            )

    return results
