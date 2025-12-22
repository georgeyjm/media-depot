from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin


class PostMedia(Base, TimestampMixin):
    '''
    Association table between Post and MediaAsset.
    '''
    __tablename__ = 'post_media'

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True)
    media_asset_id: Mapped[int] = mapped_column(ForeignKey('media_assets.id', ondelete='RESTRICT'), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Relationships
    post: Mapped['Post'] = relationship(back_populates='media_items')
    media_asset: Mapped['MediaAsset'] = relationship(back_populates='post_media_refs')

    # Constraints
    __table_args__ = (
        UniqueConstraint('post_id', 'media_asset_id', name='uq_post_media_asset'),
    )

    def __repr__(self) -> str:
        return f'<PostMedia {self.post_id} -> {self.media_asset_id}>'
