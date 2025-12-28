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
# [이슈명] 브리핑

**작성일**: YYYY년 MM월 DD일
**작성자**: DSTILL 리서치팀

---

## Executive Summary
- 핵심 내용 3줄 요약 (bullet point)

## 1. 현황 (Status)
현재 상황을 객관적 사실 중심으로 서술

## 2. 주요 팩트 (Key Facts)
| 항목 | 내용 | 출처 |
|------|------|------|
| ... | ... | 기사명 |

## 3. 타임라인 (Timeline)
- **MM/DD**: 주요 사건
- **MM/DD**: 후속 전개

## 4. 분석 (Analysis)
### 배경
### 영향
### 리스크 요인

## 5. 전망 (Outlook)
향후 예상 시나리오 및 주목 포인트

## 6. 참고 자료
- 기사 출처 목록

---
*본 보고서는 공개된 뉴스 기사를 기반으로 작성되었습니다.*
```

## 작성 규칙
1. **팩트 기반**: 기사에 있는 내용만 사용, 추측 금지
2. **출처 명시**: 주요 정보는 어느 기사에서 왔는지 표시
3. **미확인 표시**: 확인되지 않은 정보는 "(미확인)" 태그
4. **날짜 구분**: 서로 다른 날짜의 정보는 명확히 구분
5. **진행형 표시**: 수사/재판 등 진행 중 사안은 "진행 중" 명시
6. **전문적 톤**: 감정적 표현 배제, 객관적 서술
7. **분량**: 1500~2000자

## 어조 규칙 (중요!)
**판단하는 표현 금지** → **관측하는 표현 사용**

❌ 피해야 할 표현 (판단):
- "중요하다", "핵심이다", "주목할 만하다"
- "뜨겁다", "심각하다", "우려된다"
- "긍정적이다", "부정적이다", "좋다/나쁘다"

✅ 사용할 표현 (관측):
- "자주 등장한다", "반복 언급된다", "다수 보도되었다"
- "N건의 기사에서 다뤄졌다", "여러 매체에서 보도했다"
- "~로 나타났다", "~로 확인된다", "~한 것으로 보인다"
- "~라는 반응이 있다", "~라는 의견이 제기되고 있다"

예시:
- ❌ "이 사안은 매우 중요하다"
- ✅ "이 사안은 10개 이상의 매체에서 보도되었다"

- ❌ "시장의 우려가 커지고 있다"
- ✅ "우려를 표명하는 기사가 다수 확인된다"

보고서:
"""
