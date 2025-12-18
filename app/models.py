from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

db = SQLAlchemy()

class Creator(db.Model):
    '''Represents a content creator on a platform'''
    __tablename__ = 'creators'
    
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)  # e.g., 'youtube', 'tiktok'
    platform_id = db.Column(db.String(200), nullable=False)  # Unique ID on the platform
    username = db.Column(db.String(200))
    profile_pic_url = db.Column(db.String(500))  # Original URL from the platform
    profile_pic_local = db.Column(db.String(500))  # Local path to cached version
    profile_pic_last_updated = db.Column(db.DateTime, nullable=True)  # When we last updated the cache
    created_at = db.Column(db.DateTime, default=datetime.now())
    
    # Relationships
    posts = relationship('Post', back_populates='creator')
    subscriptions = relationship('Subscription', back_populates='creator')
    
    __table_args__ = (
        db.UniqueConstraint('platform', 'platform_id', name='uix_platform_creator'),
    )
    
    def get_profile_pic(self, cache_dir='profile_pics'):
        """
        Get the local path to the creator's profile picture.
        Downloads and caches the image if not already cached or if cache is stale.
        """
        import os
        import requests
        from datetime import datetime, timedelta
        
        # If we don't have a remote URL, return None
        if not self.profile_pic_url:
            return None
            
        # If we have a local copy that's less than a week old, use it
        if (self.profile_pic_local and 
            os.path.exists(self.profile_pic_local) and 
            self.profile_pic_last_updated and 
            (datetime.utcnow() - self.profile_pic_last_updated) < timedelta(days=7)):
            return self.profile_pic_local
            
        # Otherwise, download and cache the image
        try:
            # Create cache directory if it doesn't exist
            os.makedirs(cache_dir, exist_ok=True)
            
            # Determine file extension from URL or use default
            ext = 'jpg'  # default extension
            if '.' in self.profile_pic_url.split('?')[0]:
                ext = self.profile_pic_url.split('?')[0].split('.')[-1].lower()
                if len(ext) > 4:  # Sanity check for weird URLs
                    ext = 'jpg'
            
            # Generate local filename
            local_path = os.path.join(cache_dir, f"{self.platform}_{self.platform_id}.{ext}")
            
            # Download the image
            response = requests.get(self.profile_pic_url, stream=True)
            response.raise_for_status()
            
            # Save to local file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Update model
            self.profile_pic_local = local_path
            self.profile_pic_last_updated = datetime.utcnow()
            
            return local_path
            
        except Exception as e:
            # If anything fails, return None and log the error
            print(f"Failed to cache profile picture: {e}")
            return None
    
    def __repr__(self):
        return f'<Creator {self.platform}:{self.username}>'


class Post(db.Model):
    '''Represents a post from a content creator (video, image, text, etc.)'''
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.String(200), nullable=False)  # Unique ID on the platform
    creator_id = db.Column(db.Integer, db.ForeignKey('creators.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    # thumbnail_url = db.Column(db.String(500), nullable=True)  # URL to thumbnail/image
    # media_url = db.Column(db.String(500), nullable=True)  # URL to actual media (if applicable)
    created_at = db.Column(db.DateTime, default=datetime.now())
    
    # Relationships
    creator = relationship('Creator', back_populates='posts')
    subscription = relationship('Subscription', back_populates='posts')
    
    __table_args__ = (
        db.Index('ix_posts_creator_created', 'creator_id', 'created_at')
    )
    
    def __repr__(self):
        return f'<Post {self.title}>'


class Subscription(db.Model):
    '''Represents a user's subscription to a creator'''
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('creators.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    last_downloaded_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    creator = relationship('Creator', back_populates='subscriptions')
    posts = relationship('Post', back_populates='subscription')
    
    def __repr__(self):
        return f'<Subscription {self.creator_id}>'
