import hashlib
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings


router = APIRouter()

# Extensions that need conversion for browser compatibility
CONVERT_EXTENSIONS = {'.heif', '.heic', '.avif'}

# Cache subdirectory for converted images
CONVERTED_CACHE_DIR = settings.CACHE_DIR / 'converted'
CONVERTED_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(original_path: Path) -> Path:
    '''Generate a cache path for the converted file.'''
    # Use hash of the original path to avoid collisions and deep directories
    path_hash = hashlib.md5(str(original_path).encode()).hexdigest()
    return CONVERTED_CACHE_DIR / f'{path_hash}.jpg'


def convert_to_jpg(source_path: Path, dest_path: Path, quality: int = 95) -> bool:
    '''
    Convert HEIF/AVIF to JPEG using ImageMagick.

    Returns True if successful, False otherwise.
    '''
    try:
        commands = [
            ['magick', str(source_path), '-quality', str(quality), str(dest_path)],
            ['sips', '-s', 'format', 'jpeg', str(source_path), '--out', str(dest_path)],
            ['heif-convert', '--quality', str(quality), '--disable-limits', str(source_path), '--output', str(dest_path)],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, timeout=30)
            if result.returncode == 0:
                break
        else:
            print(f'Conversion failed for {source_path}')
            return False
        return dest_path.exists()
    except Exception as e:
        print(f'Conversion error for {source_path}: {e}')
        return False


# def get_mime_type(file_path: Path) -> str:
#     '''Get MIME type for a file based on extension.'''
#     ext = file_path.suffix.lower()
#     mime_types = {
#         '.jpg': 'image/jpeg',
#         '.jpeg': 'image/jpeg',
#         '.png': 'image/png',
#         '.gif': 'image/gif',
#         '.webp': 'image/webp',
#         '.heic': 'image/heic',
#         '.heif': 'image/heif',
#         '.avif': 'image/avif',
#         '.mp4': 'video/mp4',
#         '.mov': 'video/quicktime',
#         '.webm': 'video/webm',
#         '.mkv': 'video/x-matroska',
#         '.avi': 'video/x-msvideo',
#     }
#     return mime_types.get(ext, 'application/octet-stream')


@router.get('/media/{path:path}')
async def serve_media(path: str):
    '''
    Serve media files with automatic HEIF/AVIF to JPEG conversion & caching.

    Converted files are cached on disk for subsequent requests.
    '''
    file_path = settings.MEDIA_ROOT_DIR / path

    # Security: prevent path traversal
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(settings.MEDIA_ROOT_DIR.resolve())):
            raise HTTPException(status_code=403, detail='Access denied')
    except Exception:
        raise HTTPException(status_code=403, detail='Invalid path')

    if not file_path.exists():
        raise HTTPException(status_code=404, detail='File not found')

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail='Not a file')

    # Check if file needs conversion based on extension
    if file_path.suffix.lower() in CONVERT_EXTENSIONS:
        cache_path = get_cache_path(file_path)

        # Check if already cached
        if not cache_path.exists():
            # Convert and cache
            success = convert_to_jpg(file_path, cache_path)
            if not success:
                # Fallback: serve original file
                return FileResponse(
                    file_path,
                    # media_type=get_mime_type(file_path),
                )

        return FileResponse(
            cache_path,
            media_type='image/jpeg',
            filename=Path(path).with_suffix('.jpg').name
        )

    # Serve original file
    return FileResponse(
        file_path,
        # media_type=get_mime_type(file_path),
    )
