import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json

from app.core.config import settings


# 1. 뉴스 스크래핑
url = "https://news.naver.com/main/ranking/popularDay.naver"
headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

boxes = soup.select("div.rankingnews_box")

all_news = []
for box in boxes:
    press_name = box.select_one("strong.rankingnews_name").text.strip()
    articles = box.select("a.list_title")

    for article in articles:
        all_news.append({
            "press": press_name,
            "title": article.text.strip(),
            "url": article["href"]
        })

print(f"[1] 총 {len(all_news)}개 기사 수집\n")

# 2. 제목만 추출
titles = [news["title"] for news in all_news]
titles_text = "\n".join([f"{i}. {t}" for i, t in enumerate(titles)])

# 3. LLM 클러스터링 요청 (DeepSeek)
client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)


prompt = f"""아래는 오늘 네이버 뉴스 랭킹에 오른 {len(titles)}개 기사 제목입니다.

이 제목들을 분석해서 현재 가장 주목받는 이슈 10개를 추출해주세요.

규칙:
1. 같은 사건/이슈를 다룬 기사들은 하나로 묶기
2. 많이 언급될수록 중요한 이슈
3. 각 이슈에 대해: 이슈명(검색 키워드로 쓸 수 있게 간결하게), 요약(1-2문장), 관련 기사 인덱스 배열, 카테고리

JSON 형식으로 응답:
{{
  "issues": [
    {{
      "name": "이슈명",
      "summary": "요약",
      "article_indices": [0, 5, 12],
      "category": "카테고리"
    }}
  ]
}}

기사 제목:
{titles_text}
"""

print("[2] LLM 클러스터링 중...\n")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"}
)

result = json.loads(response.choices[0].message.content)
issues = result["issues"]

print(f"[2] {len(issues)}개 이슈 추출 완료\n")

# 4. 네이버 검색 API로 본문 수집
NAVER_CLIENT_ID = settings.NAVER_CLIENT_ID
NAVER_CLIENT_SECRET = settings.NAVER_CLIENT_SECRET


def search_naver_news(query, display=3):
    """네이버 뉴스 검색 API"""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": display,
        "sort": "sim"  # 정확도순
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        print(f"API 에러: {response.status_code}")
        return []


print("[3] 네이버 검색 API로 본문 수집 중...\n")

for issue in issues:
    articles = search_naver_news(issue["name"], display=3)
    issue["articles"] = articles

print("[3] 본문 수집 완료\n")

# 5. 결과 출력
print("=" * 60)
print("오늘의 주요 이슈 TOP 10")
print("=" * 60)

for i, issue in enumerate(issues, 1):
    print(f"\n{'=' * 60}")
    print(f"[{i}] {issue['name']}")
    print(f"{'=' * 60}")
    print(f"카테고리: {issue['category']}")
    print(f"클러스터 기사 수: {len(issue['article_indices'])}건")
    print(f"요약: {issue['summary']}")

    print(f"\n📰 관련 기사 (네이버 검색 API):")
    for j, article in enumerate(issue.get("articles", []), 1):
        # HTML 태그 제거
        title = BeautifulSoup(article["title"], "html.parser").get_text()
        desc = BeautifulSoup(article["description"], "html.parser").get_text()

        print(f"\n  [{j}] {title}")
        print(f"      {desc[:100]}...")
        print(f"      링크: {article['link']}")