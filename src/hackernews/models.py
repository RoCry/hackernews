from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Comment(BaseModel):
    id: int
    text: str
    by: Optional[str] = None
    time: datetime
    kids: List[int] = Field(default_factory=list)
    parent: Optional[int] = None
    deleted: bool = False
    dead: bool = False
    replies: List["Comment"] = Field(default_factory=list)

    def format_tree(self, max_length: int, depth: int = 0) -> List[str]:
        lines = []
        indent = "  " * depth
        text = self.text[:max_length]
        truncated_chars = max(0, len(self.text) - max_length)
        text = text.replace("\n", f"\n{indent}  ")
        lines.append(
            f"{indent}- {self.by}: {text}"
            + (f" [+{truncated_chars} chars]" if truncated_chars > 0 else "")
        )

        for reply in self.replies:
            lines.extend(reply.format_tree(max_length, depth + 1))
        return lines


class Story(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    text: Optional[str] = None
    by: str
    time: datetime
    score: int
    descendants: int = 0
    kids: List[int] = Field(default_factory=list)
    comments: List[Comment] = Field(default_factory=list)

    def tree_string(self, max_length: int = 140) -> str:
        """Generate a tree-like string representation of the story and its comments."""

        lines = []

        # Story header
        lines.append(
            f"\n{self.title} by {self.by} @ {self.time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append(f"Content: {self.text if self.text else '[no text]'}")
        lines.append(f"Score: {self.score}, Comments: {self.descendants}")
        if self.url:
            lines.append(f"URL: {self.url}")

        # Comments section
        if self.comments:
            lines.append("\nComments:")
            for comment in self.comments:
                lines.extend(comment.format_tree(max_length))

        return "\n".join(lines)


class HNResponse(BaseModel):
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    stories: List[Story] = Field(default_factory=list)
