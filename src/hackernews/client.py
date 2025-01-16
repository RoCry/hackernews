from datetime import datetime, timezone
from typing import List, Dict, Any
import asyncio
import httpx
from .models import Story, Comment, HNResponse
from .utils import normalize_html, logger


class HackerNewsClient:
    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(
        self,
        max_concurrent_requests: int = 5,
        timeout: float = 30.0,
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def _make_request(self, url: str) -> Dict[str, Any]:
        async with self.semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()

    async def _get_top_story_ids(self, limit: int = 10) -> List[int]:
        url = f"{self.BASE_URL}/topstories.json"
        story_ids = await self._make_request(url)
        return story_ids[:limit]

    async def _get_item(self, item_id: int) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/item/{item_id}.json"
        return await self._make_request(url)

    async def _ids_to_comments(
        self, story_id: int, comment_ids: List[int], depth: int = 0, max_depth: int = 2
    ) -> List[Comment]:
        if not comment_ids:
            return []
        if max_depth != 0 and depth > max_depth:
            return []

        logger.debug(f"GET S({story_id}) L{depth} comments: {len(comment_ids)}")
        tasks = []
        for comment_id in comment_ids:
            tasks.append(self._get_item(comment_id))

        comments_data = await asyncio.gather(*tasks)
        comments = []

        for comment_data in comments_data:
            if (
                not comment_data
                or comment_data.get("deleted")
                or comment_data.get("dead")
            ):
                continue

            child_comments = await self._ids_to_comments(
                story_id, comment_data.get("kids", []), depth + 1, max_depth=max_depth
            )

            comment = Comment(
                id=comment_data["id"],
                text=normalize_html(comment_data.get("text", "")),
                by=comment_data.get("by"),
                time=datetime.fromtimestamp(comment_data["time"]),
                kids=comment_data.get("kids", []),
                parent=comment_data.get("parent"),
                deleted=comment_data.get("deleted", False),
                dead=comment_data.get("dead", False),
                replies=child_comments,
            )
            comments.append(comment)

        return comments

    ############################################################
    # Public methods
    ############################################################
    async def fetch_story(self, story_id: int, comment_depth: int = 2) -> Story:
        logger.debug(f"GET S({story_id})")
        story_data = await self._get_item(story_id)
        comments = []
        if comment_depth != 0:
            request_comments_ids = story_data.get("kids", [])
            comments = await self._ids_to_comments(
                story_id, request_comments_ids, max_depth=comment_depth
            )

        story = Story(
            id=story_data["id"],
            title=story_data["title"],
            url=story_data.get("url"),
            text=normalize_html(story_data.get("text", "")),
            by=story_data["by"],
            time=datetime.fromtimestamp(story_data["time"]),
            score=story_data["score"],
            descendants=story_data.get("descendants", 0),
            kids=story_data.get("kids", []),
            comments=comments,
        )
        logger.debug(
            f"GET S({story_id}): {len(comments)}/{len(request_comments_ids)} L0 comments(total {story_data.get('descendants', 0)})"
        )
        return story

    async def fetch_top_stories(
        self, top_n: int = 10, comment_depth: int = 2
    ) -> HNResponse:
        logger.info(f"GET TOP {top_n} stories")
        story_ids = await self._get_top_story_ids(limit=top_n)

        tasks = []
        for story_id in story_ids:
            tasks.append(self._id_to_story(story_id, comment_depth=comment_depth))

        stories = await asyncio.gather(*tasks)
        logger.info(f"GET TOP {top_n} stories: {len(stories)}")

        return HNResponse(updated_at=datetime.now(timezone.utc), stories=stories)
