from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import asyncio
import httpx
from .models import Story, Comment, HNResponse
from .utils import normalize_html, logger
from .db import HNCache


class HackerNewsClient:
    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(
        self,
        max_concurrent_requests: int = 5,
        timeout: float = 30.0,
        cache_db_path: Optional[str] = None,
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.cache = HNCache(cache_db_path) if cache_db_path else None

    async def __aenter__(self):
        if self.cache:
            await self.cache.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.cache:
            await self.cache.close()
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
        # Try to get from cache first
        if self.cache:
            cached_item = await self.cache.get_item(item_id)
            if cached_item:
                # logger.debug(f"Cache hit for item {item_id}")
                return cached_item

        # If not in cache or no cache configured, fetch from network
        url = f"{self.BASE_URL}/item/{item_id}.json"
        data = await self._make_request(url)

        # Save to cache if available
        if self.cache and data:
            await self.cache.save_item(item_id, data)

        return data

    # depth: 0 -> root comment
    # fetch_comment_levels_count: how many levels of comments to fetch
    #   0 -> do not fetch any comments, 1 only root comments, 2 -> root + first level of replies
    async def _ids_to_comments(
        self,
        story_id: int,
        comment_ids: List[int],
        depth: int = 0,
        fetch_comment_levels_count: int = 2,
    ) -> List[Comment]:
        if not comment_ids:
            return []
        if fetch_comment_levels_count != 0 and depth >= fetch_comment_levels_count:
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
                story_id,
                comment_data.get("kids", []),
                depth + 1,
                fetch_comment_levels_count=fetch_comment_levels_count,
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
    async def fetch_story(
        self, story_id: int, fetch_comment_levels_count: int = 2
    ) -> Story:
        logger.debug(f"GET S({story_id})")
        story_data = await self._get_item(story_id)
        comments = []
        if fetch_comment_levels_count != 0:
            request_comments_ids = story_data.get("kids", [])
            comments = await self._ids_to_comments(
                story_id,
                request_comments_ids,
                fetch_comment_levels_count=fetch_comment_levels_count,
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
        self, top_n: int = 10, fetch_comment_levels_count: int = 2
    ) -> HNResponse:
        logger.info(f"GET TOP {top_n} stories")
        story_ids = await self._get_top_story_ids(limit=top_n)

        tasks = []
        for story_id in story_ids:
            tasks.append(
                self.fetch_story(
                    story_id, fetch_comment_levels_count=fetch_comment_levels_count
                )
            )

        stories = await asyncio.gather(*tasks)
        logger.info(f"GET TOP {top_n} stories: {len(stories)}")

        return HNResponse(updated_at=datetime.now(timezone.utc), stories=stories)
