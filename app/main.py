from flask import Flask, render_template, request, jsonify
from models import db, Post, Creator, Subscription, Post
from handlers import get_handler_for_url
import os
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///media_crawler.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the app
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Get filter parameters
    post_type = request.args.get('type')
    creator_id = request.args.get('creator_id')
    
    # Build query
    query = Post.query
    
    if post_type:
        query = query.filter(Post.post_type == post_type)
    if creator_id:
        query = query.filter(Post.creator_id == creator_id)
    
    # Order by creation date (newest first)
    posts = query.order_by(Post.created_at.desc()).all()
    
    # Get all creators for filter dropdown
    creators = Creator.query.order_by(Creator.username).all()
    
    return render_template('index.html', 
                         posts=posts, 
                         creators=creators,
                         current_type=post_type,
                         current_creator_id=creator_id)

@app.route('/crawl', methods=['POST'])
def crawl():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        # Get appropriate handler for the URL
        handler = get_handler_for_url(url)
        
        # Extract post information
        post_info = handler.extract_info(url)
        
        # Create downloads directory if it doesn't exist
        download_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
        os.makedirs(download_path, exist_ok=True)
        
        # Download the media if needed
        download_result = None
        if handler.should_download_media():
            download_result = handler.download(url, download_path)
        
        # Create or get creator
        creator = Creator.query.filter_by(
            platform=post_info.get('platform'),
            platform_id=post_info.get('creator_id')
        ).first()
        
        if not creator:
            creator = Creator(
                platform=post_info.get('platform'),
                platform_id=post_info.get('creator_id'),
                username=post_info.get('creator_username'),
                profile_pic_url=post_info.get('creator_avatar'),
                created_at=datetime.utcnow()
            )
            db.session.add(creator)
            db.session.flush()  # To get the creator ID
        
        # Create post
        post = Post(
            platform_id=post_info['platform_id'],
            creator_id=creator.id,
            post_type=post_info.get('post_type', Post.TYPE_OTHER),
            title=post_info.get('title', ''),
            description=post_info.get('description'),
            url=url,
            thumbnail_url=post_info.get('thumbnail_url'),
            media_url=post_info.get('media_url'),
            duration=post_info.get('duration'),
            width=post_info.get('width'),
            height=post_info.get('height'),
            created_at=post_info.get('created_at', datetime.utcnow())
        )
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({
            'message': 'Post crawled successfully',
            'post': {
                'id': post.id,
                'title': post.title,
                'type': post.post_type,
                'creator': creator.username,
                'created_at': post.created_at.isoformat()
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
