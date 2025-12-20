from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.agent.tools.base import TrendProvider, TrendItem
from app.core.config import settings
import time
from typing import TypedDict


class YouTubeAPIError(Exception):
    """YouTube API 에러"""
    pass


class CommentItem(TypedDict):
    """댓글 구조"""
    text: str
    like_count: int
    author: str
    published_at: str


class YouTubeProvider(TrendProvider):
    """YouTube 트렌드 Provider"""

    def __init__(self):
        if not settings.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY가 설정되지 않았습니다.")
        self.youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)

    @property
    def source_type(self) -> str:
        return "youtube"

    async def get_trending(
            self,
            country: str = "KR",
            max_results: int = 50,
            max_retries: int = 3
    ) -> list[TrendItem]:
        """YouTube 인기 급상승 가져오기"""

        for attempt in range(max_retries):
            try:
                # 인기 급상승 영상 가져오기
                request = self.youtube.videos().list(
                    part="snippet,statistics",
                    chart="mostPopular",
                    regionCode=country,
                    maxResults=min(max_results, 50)
                )
                response = request.execute()

                items = response.get("items", [])

                if not items:
                    print(f"트렌드 결과 없음: {country}")
                    return []

                # 각 영상의 상세 정보 (태그 포함) 가져오기
                video_ids = [item["id"] for item in items]
                details = self._get_video_details(video_ids)

                return [
                    TrendItem(
                        title=item["snippet"]["title"],
                        url=f"https://www.youtube.com/watch?v={item['id']}",
                        channel_name=item["snippet"]["channelTitle"],
                        channel_id=item["snippet"]["channelId"],
                        video_id=item["id"],
                        view_count=int(item["statistics"].get("viewCount", 0)),
                        like_count=int(item["statistics"].get("likeCount", 0)),
                        comment_count=int(item["statistics"].get("commentCount", 0)),
                        published_at=item["snippet"]["publishedAt"],
                        thumbnail_url=item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
                        description=item["snippet"].get("description", ""),
                        tags=details.get(item["id"], {}).get("tags", [])
                    )
                    for item in items
                ]

            except HttpError as e:
                error_msg = str(e).lower()

                if "quotaexceeded" in error_msg or "403" in str(e.resp.status):
                    print("YouTube API 할당량 초과")
                    raise YouTubeAPIError("API quota exceeded")

                if "rateLimitExceeded" in error_msg or e.resp.status == 429:
                    wait_time = (attempt + 1) * 5
                    print(f"Rate limited. {wait_time}초 대기... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                if "forbidden" in error_msg or e.resp.status == 401:
                    print("YouTube API 키가 유효하지 않습니다.")
                    raise YouTubeAPIError("Invalid API key")

                print(f"YouTube API 에러: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return []

            except Exception as e:
                print(f"YouTube 에러: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return []

        print(f"YouTube 트렌드 실패: 최대 재시도 횟수 초과 ({max_retries}회)")
        return []

    def _get_video_details(self, video_ids: list[str]) -> dict:
        """영상 상세 정보 (태그 등) 가져오기"""
        try:
            request = self.youtube.videos().list(
                part="snippet",
                id=",".join(video_ids)
            )
            response = request.execute()

            return {
                item["id"]: {
                    "tags": item["snippet"].get("tags", [])
                }
                for item in response.get("items", [])
            }
        except Exception as e:
            print(f"영상 상세 정보 가져오기 실패: {e}")
            return {}

    async def get_top_comments(
            self,
            video_id: str,
            max_results: int = 10,
            max_retries: int = 3
    ) -> list[CommentItem]:
        """영상의 인기 댓글 가져오기 (좋아요 순)"""

        for attempt in range(max_retries):
            try:
                request = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    order="relevance",  # 관련성 순 (좋아요 많은 것 우선)
                    maxResults=min(max_results, 100)
                )
                response = request.execute()

                items = response.get("items", [])

                if not items:
                    return []

                comments = []
                for item in items:
                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append(CommentItem(
                        text=snippet["textDisplay"],
                        like_count=snippet.get("likeCount", 0),
                        author=snippet["authorDisplayName"],
                        published_at=snippet["publishedAt"]
                    ))

                # 좋아요 순 정렬 (API가 완벽하게 정렬 안 해줄 수 있어서)
                comments.sort(key=lambda x: x["like_count"], reverse=True)

                return comments[:max_results]

            except HttpError as e:
                error_msg = str(e).lower()

                # 댓글 비활성화된 영상
                if "commentsdisabled" in error_msg or "403" in str(e.resp.status):
                    print(f"댓글 비활성화: {video_id}")
                    return []

                if "quotaexceeded" in error_msg:
                    print("YouTube API 할당량 초과")
                    raise YouTubeAPIError("API quota exceeded")

                print(f"댓글 가져오기 에러: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return []

            except Exception as e:
                print(f"댓글 에러: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return []

        return []