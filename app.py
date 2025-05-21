from flask import Flask, render_template, request, jsonify
from models import db, Video, Creator, Subscription
from handlers.handler_factory import get_handler_for_url
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///media_crawler.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the app
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return render_template('index.html', videos=videos)

@app.route('/crawl', methods=['POST'])
def crawl():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        # Get appropriate handler for the URL
        handler = get_handler_for_url(url)
        
        # Extract video information
        video_info = handler.extract_info(url)
        
        # Download the video
        download_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
        os.makedirs(download_path, exist_ok=True)
        download_result = handler.download(url, download_path)
        
        # Add video to database
        video = Video(
            title=video_info['title'],
            url=url,
            source=handler.__class__.__name__.replace('Handler', '').lower(),
            description=video_info['description'],
            thumbnail=video_info['thumbnail'],
            duration=str(video_info.get('duration', 'N/A'))
        )
        db.session.add(video)
        db.session.commit()
        
        return jsonify({
            'message': 'Video crawled successfully',
            'video': {
                'id': video.id,
                'title': video.title,
                'source': video.source,
                'duration': video.duration,
                'thumbnail': video.thumbnail
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
