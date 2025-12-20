import asyncio
from googleapiclient.discovery import build
from app.core.config import settings


async def search_and_analyze(keyword: str):
    youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)

    print(f"=" * 60)
    print(f"키워드: {keyword}")
    print(f"=" * 60)

    # 1. 키워드 검색 (최근 업로드, 조회수 순)
    search_request = youtube.search().list(
        part="snippet",
        q=keyword,
        type="video",
        order="viewCount",  # 조회수 순
        publishedAfter="2024-12-01T00:00:00Z",  # 최근 영상만
        regionCode="KR",
        maxResults=5
    )
    search_response = search_request.execute()

    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

    if not video_ids:
        print("검색 결과 없음")
        return

    # 2. 영상 상세 정보 (조회수, 좋아요)
    videos_request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    )
    videos_response = videos_request.execute()

    for item in videos_response.get("items", []):
        video_id = item["id"]
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        view_count = int(item["statistics"].get("viewCount", 0))
        like_count = int(item["statistics"].get("likeCount", 0))

        print(f"\n[영상] {title}")
        print(f"  채널: {channel}")
        print(f"  조회수: {view_count:,} / 좋아요: {like_count:,}")
        print(f"  URL: https://youtube.com/watch?v={video_id}")

        # 3. 댓글 수집
        try:
            comments_request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                maxResults=5
            )
            comments_response = comments_request.execute()

            comments = comments_response.get("items", [])
            if comments:
                print(f"\n  📝 인기 댓글:")
                for c in comments:
                    snippet = c["snippet"]["topLevelComment"]["snippet"]
                    text = snippet["textDisplay"][:80].replace("\n", " ")
                    likes = snippet.get("likeCount", 0)
                    print(f"    [{likes:,}👍] {text}...")
            else:
                print(f"\n  📝 댓글 없음")
        except Exception as e:
            print(f"\n  📝 댓글 비활성화")


if __name__ == "__main__":
    asyncio.run(search_and_analyze("쿠팡 해킹"))