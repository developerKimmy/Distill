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
    """블로그 제목 생성 프롬프트"""
    return f"""이슈: {issue_name}
사람들이 궁금해하는 것: {', '.join(needs[:3])}

위 내용을 바탕으로 블로그 제목을 하나만 생성해주세요.
- 클릭하고 싶게 만드는 제목
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
    """블로그 콘텐츠 생성 프롬프트"""
    return f"""이슈: {issue_name}
기준일자: {today_str}

## 참고 기사
{articles_text}

## 관련 키워드
{', '.join(keywords) if keywords else '없음'}

## 사람들이 궁금해하는 것 (니즈)
{needs_text}

## 추천 콘텐츠 방향
{directions_text}

## 관련 데이터 (날짜별 정보 - 날짜 구분 필수)
{similar_text}

---

위 정보를 바탕으로 블로그 글을 작성해주세요.

규칙:
1. 반드시 위 기사 내용에 있는 팩트만 사용하세요
2. 기사에 없는 수치나 정보는 절대 추측하지 마세요
3. 사람들이 궁금해하는 것(니즈)에 답하는 형태로 작성하세요
4. 확인되지 않은 정보는 "[미확인]" 태그를 붙여주세요
5. 마크다운 형식으로 작성하세요
6. 1500~2000자 내외로 작성하세요

날짜별 데이터 처리 규칙 (중요!):
7. 관련 데이터에 "(MM/DD 기준)" 형태로 날짜가 표시되어 있습니다
8. 같은 항목이라도 날짜별로 다른 수치가 있으면 시간순으로 변화를 설명하세요
   - 예: "24일 30% 상승 → 25일 15% 하락 → 26일 20% 반등"
9. 서로 다른 날짜의 수치를 섞거나 평균내지 마세요
10. 가장 최신 정보를 기준으로 하되, 변화 추이가 있으면 함께 설명하세요

진행형 사건 처리 규칙:
11. 수사/재판/협상 등 진행 중인 사건은 "현재 진행 중"임을 명시하세요
12. 후속 전개가 예상되는 경우 "향후 ~가 예정되어 있다" 등으로 표시하세요
13. 기사 발행일 기준으로 "~일 기준" 또는 "~시점 기준"을 명확히 표시하세요
14. 결론이 나지 않은 사안은 단정짓지 말고 "~할 전망이다", "~가 주목된다" 등으로 마무리하세요

블로그 글:
"""
