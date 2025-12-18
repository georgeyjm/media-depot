'''Douyin media handler module.'''
from typing import Dict, Any
import re
import os
import requests
from bs4 import BeautifulSoup

patterns = (
    r'https?:\/\/v\.douyin\.com\/[\w-]+\/',
)

def extract_supported_url(url: str) -> str | None:
    '''Return the URL supported by this handler, or None if not supported.'''
    for pattern in patterns:
        if match := re.match(pattern, url):
            return match.group()
    return None

def extract_info(url: str) -> Dict[str, Any]:
    '''Extract video information from TikTok.'''
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract title and description
    title = soup.find('meta', property='og:title')['content']
    description = soup.find('meta', property='og:description')['content']
    
    # Extract thumbnail
    thumbnail = soup.find('meta', property='og:image')['content']
    
    return {
        'title': title,
        'description': description,
        'thumbnail': thumbnail,
        'duration': None  # TikTok API doesn't provide duration easily
    }

def download(url: str, output_path: str) -> str:
    '''Download TikTok video.'''
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # First get video info to get the title for the filename
    info = extract_info(url)
    
    # Get the video page
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract video URL from script tags
    scripts = soup.find_all('script')
    video_url = None
    
    for script in scripts:
        if script.string and 'playAddr' in script.string:
            try:
                # Extract video URL from JSON-like string
                start = script.string.find('playAddr\\":\"') + len('playAddr\\":\"')
                end = script.string.find('\"', start)
                video_url = script.string[start:end].replace('\\u0026', '&')
                break
            except Exception as e:
                print(f'Error extracting video URL: {e}')
                continue
    
    if not video_url:
        raise Exception('Could not find video URL in page')
    
    # Ensure output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Download the video
    video_response = requests.get(video_url, headers=headers, stream=True, timeout=30)
    video_response.raise_for_status()
    
    # Create a safe filename
    safe_title = ''.join(c if c.isalnum() or c in ' ._-' else '_' for c in info['title'])
    filename = os.path.join(output_path, f'{safe_title}.mp4')
    
    with open(filename, 'wb') as f:
        for chunk in video_response.iter_content(chunk_size=8192):
            if chunk:  # filter out keep-alive chunks
                f.write(chunk)
    
    return filename
