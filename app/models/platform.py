from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin


class Platform(Base, TimestampMixin):
    __tablename__ = 'platforms'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., 'YouTube', 'TikTok'
    # api_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Base URL for platform API
    # is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    creators: Mapped[list['Creator']] = relationship(back_populates='platform', cascade='all, delete-orphan')
    posts: Mapped[list['Post']] = relationship(back_populates='platform', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f'<Platform {self.name}>'
