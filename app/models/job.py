from typing import Any, Optional

from sqlalchemy import String, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Base, TimestampMixin
from app.models.enums import JobStatus


class Job(Base, TimestampMixin):
    __tablename__ = 'jobs'

    id: Mapped[int] = mapped_column(primary_key=True)
    share_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    share_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[JobStatus] = mapped_column(nullable=False, default=JobStatus.pending)
    post_id: Mapped[Optional[int]] = mapped_column(ForeignKey('posts.id', ondelete='CASCADE'), nullable=True)  # Post is only attached after URL resolution
    error: Mapped[Optional[dict[str, Any]]] = mapped_column('error', JSONB, default=dict, nullable=True)

    # Relationships
    post: Mapped['Post'] = relationship(back_populates='jobs')

    # Constraints and indexes
    __table_args__ = (
        Index('ix_jobs_url_status', 'share_url', 'status'),
        Index('ix_jobs_post_status', 'post_id', 'status'),
    )

    def __repr__(self) -> str:
        return f'<Job {self.id}:{self.status}>'

