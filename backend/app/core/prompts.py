"""
프롬프트 템플릿 모음

모든 LLM 프롬프트를 한 곳에서 관리합니다.
"""


def clustering_prompt(
    titles: list[str],
    existing_issues: list[str] | None = None,
    num_issues: int = 10
) -> str:
    """뉴스 클러스터링 프롬프트"""
    titles_text = "\n".join([f"{i}. {t}" for i, t in enumerate(titles)])

    existing_text = ""
    if existing_issues:
        existing_text = f"""
기존에 추적 중인 이슈 목록:
{chr(10).join([f"- {name}" for name in existing_issues])}

위 이슈에 해당하는 기사가 있으면 반드시 해당 이슈명을 그대로 사용하세요.
새로운 이슈인 경우에만 새 이름을 만드세요.
"""

    return f"""아래는 오늘 네이버 뉴스 랭킹에 오른 {len(titles)}개 기사 제목입니다.

이 제목들을 분석해서 현재 가장 주목받는 이슈 {num_issues}개를 추출해주세요.
{existing_text}
규칙:
1. 같은 사건/이슈를 다룬 기사들은 하나로 묶기
2. 많이 언급될수록 중요한 이슈
3. 각 이슈에 대해:
   - name: 이슈명 (검색 키워드로 쓸 수 있게 간결하게)
   - summary: 요약 (1-2문장)
   - article_indices: 관련 기사 인덱스 배열
   - category: 카테고리 (정치, 경제, 사회, 세계, 연예, IT/과학)
   - issue_type: "ongoing" (수사/재판/협상 등 진행 중) 또는 "concluded" (이미 종결된 사건)
   - related_search_terms: 후속 검색에 사용할 핵심 엔티티 (인물명, 기관명 등) 1~3개

JSON 형식으로 응답:
{{
  "issues": [
    {{
      "name": "이슈명",
      "summary": "요약",
      "article_indices": [0, 5, 12],
      "category": "카테고리",
      "issue_type": "ongoing",
      "related_search_terms": ["인물명", "기관명"]
    }}
  ]
}}

기사 제목:
{titles_text}
"""


def keyword_extraction_prompt(issue_name: str, articles_text: str) -> str:
    """키워드 추출 프롬프트"""
    return f"""이슈: {issue_name}

아래는 이 이슈 관련 기사들입니다.

{articles_text}

---

이 기사들에서 블로그 콘텐츠 작성에 활용할 수 있는 구체적인 키워드를 추출해주세요.

규칙:
1. 구체적인 수치/금액이 포함된 키워드 (예: "과징금 1500억", "3370만건 유출")
2. 비교 대상 (예: "SKT 해킹 비교")
3. 후속 이슈 (예: "집단소송", "주가 전망")
4. 관련 인물/기관 (예: "개인정보보호위원회")
5. 5~10개 추출

JSON 형식으로 응답:
{{
  "keywords": ["키워드1", "키워드2", ...]
}}
"""


def needs_extraction_prompt(issue_name: str, comments_text: str) -> str:
    """니즈 추출 프롬프트"""
    return f"""이슈: {issue_name}

아래는 이 이슈 관련 YouTube 영상들의 인기 댓글입니다.

{comments_text}

---

이 댓글들을 분석해서:

1. **니즈**: 사람들이 궁금해하는 것, 알고 싶어하는 것 (5~10개)
   - 질문 형태로 정리 (예: "과징금 나오면 쿠팡 망하나?")

2. **콘텐츠 방향**: 이 니즈를 해결할 블로그 글 주제 (3~5개)
   - 구체적인 제목 형태로 (예: "쿠팡 해킹 과징금 전망과 주가 영향 분석")

JSON 형식으로 응답:
{{
  "needs": ["니즈1", "니즈2", ...],
  "content_directions": ["제목1", "제목2", ...]
}}
"""


def title_generation_prompt(issue_name: str, needs: list[str]) -> str:
    """보고서 제목 생성 프롬프트"""
    return f"""이슈: {issue_name}
핵심 관심사: {', '.join(needs[:3])}

위 내용을 바탕으로 브리핑 보고서 제목을 하나만 생성해주세요.
- 전문적이고 명확한 제목
- 예: "[이슈명] 현황 분석 및 전망", "[이슈명] 동향 브리핑"
- 30자 내외
- 제목만 출력 (다른 설명 없이)
"""


def content_generation_prompt(
    issue_name: str,
    today_str: str,
    articles_text: str,
    keywords: list[str],
    needs_text: str,
    directions_text: str,
    similar_text: str
) -> str:
    """이슈 브리핑 보고서 생성 프롬프트"""
    return f"""이슈: {issue_name}
기준일자: {today_str}

## 참고 기사
{articles_text}

## 관련 키워드
{', '.join(keywords) if keywords else '없음'}

## 핵심 관심사
{needs_text}

## 분석 방향
{directions_text}

## 과거 데이터 (날짜별)
{similar_text}

---

위 정보를 바탕으로 **이슈 브리핑 보고서**를 작성해주세요.

## 보고서 형식 (반드시 준수)

```
# 이슈명

**작성일**: YYYY년 MM월 DD일

---

## 한줄 요약
이슈의 핵심을 한 문장으로

## 현황
- 현재 상황을 팩트 중심으로 bullet point
- 출처는 괄호로 표기 (예: 연합뉴스)

## 주요 팩트
| 항목 | 내용 | 출처 |
|------|------|------|
| ... | ... | 기사명 |

## 사람들이 궁금해하는 것
핵심 관심사에서 추출한 질문들과 그에 대한 답변

### Q. [질문1]
→ [기사/데이터 기반 답변]

### Q. [질문2]
→ [기사/데이터 기반 답변]

### Q. [질문3]
→ [기사/데이터 기반 답변]

## 앞으로 주목할 점
- 향후 일정이나 변수를 bullet point로
```

## 작성 규칙
1. **팩트만**: 기사에 있는 내용만, 추측 금지
2. **출처 표기**: (기사명) 형태로
3. **판단 금지**: "중요하다", "심각하다" 같은 판단 표현 사용 금지
4. **Q&A 핵심**: "사람들이 궁금해하는 것" 섹션이 보고서의 핵심. 핵심 관심사의 질문에 기사 내용으로 명확히 답변
5. **분량**: 800~1200자

보고서:
"""


def daily_digest_prompt(date_str: str, issues_by_category: dict[str, list[dict]]) -> str:
    """일간 다이제스트 요약 프롬프트"""

    issues_text = ""
    for category, issues in issues_by_category.items():
        issues_text += f"\n### {category}\n"
        for issue in issues:
            issues_text += f"- **{issue['name']}**: {issue['summary']}\n"
            if issue.get('content_summary'):
                issues_text += f"  - 핵심: {issue['content_summary']}\n"

    return f"""날짜: {date_str}

오늘 수집된 이슈들:
{issues_text}

---

위 이슈들을 바탕으로 **일간 브리핑 다이제스트**를 작성해주세요.

## 형식

```
# MM월 DD일 브리핑

## 오늘의 핵심
- 가장 주목할 이슈 3개를 한 문장씩 요약

---

## 정치
### 이슈명
한줄 요약

### 이슈명
한줄 요약

## 경제
### 이슈명
한줄 요약

(카테고리별로 계속)

---

*DSTILL 리서치팀*
```

## 규칙
1. **카테고리별 정리**: 정치, 경제, 사회, 세계, 연예, IT/과학 순서
2. **간결하게**: 각 이슈당 1-2문장
3. **판단 금지**: "중요하다", "심각하다" 등 판단 표현 사용 금지
4. **팩트 중심**: 있는 그대로만 서술

다이제스트:
"""
