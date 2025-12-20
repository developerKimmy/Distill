# backend/app/core/agent/nodes.py

from langchain_openai import ChatOpenAI
from app.core.agent.state import AgentState
from app.core.agent.tools import TavilyProvider
from app.core.config import settings

# LLM 설정 (DeepSeek)
llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# 검색 도구
search_provider = TavilyProvider()


async def planning_node(state: AgentState) -> dict:
    """계획 수립 노드"""
    query = state["query"]

    # 이미 에러가 있으면 스킵
    if state.get("error"):
        return {}

    try:
        response = await llm.ainvoke(
            f"""사용자 질문을 분석하고 검색 계획을 세워주세요.

질문: {query}

다음 형식으로 답변:
1. 검색할 키워드 (쉼표로 구분)
2. 예상되는 정보 유형
"""
        )

        return {
            "plan": response.content,
            "current_step": "planning"
        }
    except Exception as e:
        return {
            "error": f"계획 수립 실패: {str(e)}",
            "current_step": "error"
        }


async def search_node(state: AgentState) -> dict:
    """검색 노드"""
    query = state["query"]

    # 이미 에러가 있으면 스킵
    if state.get("error"):
        return {}

    try:
        results = await search_provider.search(query, max_results=5)

        # 검색 결과가 없을 때 처리
        if not results:
            return {
                "search_results": [],
                "current_step": "search_failed",
                "error": f"검색 결과를 찾을 수 없습니다: '{query}'"
            }

        # SearchResult를 dict로 변환
        search_results = [
            {
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
                "source_type": r["source_type"],
                "score": r.get("score", 0.0),
                "published_date": r.get("published_date")
            }
            for r in results
        ]

        return {
            "search_results": search_results,
            "current_step": "searching"
        }
    except Exception as e:
        return {
            "search_results": [],
            "error": f"검색 실패: {str(e)}",
            "current_step": "error"
        }


async def analyze_node(state: AgentState) -> dict:
    """분석 노드"""
    query = state["query"]
    search_results = state.get("search_results", [])

    # 에러가 있거나 검색 결과가 없으면 스킵
    if state.get("error"):
        return {}

    if not search_results:
        return {
            "analysis": "",
            "error": "분석할 검색 결과가 없습니다.",
            "current_step": "error"
        }

    try:
        # 검색 결과 포맷팅
        results_text = "\n\n".join([
            f"[{i + 1}] 제목: {r['title']}\nURL: {r['url']}\n내용: {r['snippet']}"
            for i, r in enumerate(search_results)
        ])

        response = await llm.ainvoke(
            f"""다음 검색 결과를 분석해주세요.

질문: {query}

검색 결과:
{results_text}

중요: 검색 결과에 있는 정보만 사용해서 분석해주세요.
검색 결과에 없는 내용은 "해당 정보를 찾을 수 없습니다"라고 명시해주세요.
"""
        )

        return {
            "analysis": response.content,
            "current_step": "analyzing"
        }
    except Exception as e:
        return {
            "analysis": "",
            "error": f"분석 실패: {str(e)}",
            "current_step": "error"
        }


async def report_node(state: AgentState) -> dict:
    """리포트 생성 노드"""
    query = state["query"]
    analysis = state.get("analysis", "")
    search_results = state.get("search_results", [])
    error = state.get("error")

    # 에러가 있으면 에러 리포트 생성
    if error:
        return {
            "final_report": f"""# 리서치 실패

**질문**: {query}

**오류**: {error}

검색 또는 분석 과정에서 문제가 발생했습니다.
다른 검색어로 다시 시도해주세요.
""",
            "current_step": "completed"
        }

    # 정상 리포트 생성
    try:
        # 출처 목록
        sources = "\n".join([
            f"- [{r['title']}]({r['url']})"
            for r in search_results
        ])

        response = await llm.ainvoke(
            f"""다음 분석을 바탕으로 최종 리포트를 작성해주세요.

질문: {query}

분석 내용:
{analysis}

중요 지침:
1. 분석 내용에 기반해서만 작성하세요
2. 검색 결과에 없는 정보는 추측하지 마세요
3. 불확실한 정보는 "추가 확인 필요"라고 표시하세요

마크다운 형식으로 깔끔하게 작성해주세요.
마지막에 참고 출처를 포함하세요.
"""
        )

        # 출처 추가
        final_report = f"{response.content}\n\n---\n\n## 참고 출처\n{sources}"

        return {
            "final_report": final_report,
            "current_step": "completed"
        }
    except Exception as e:
        return {
            "final_report": f"리포트 생성 실패: {str(e)}",
            "current_step": "error"
        }