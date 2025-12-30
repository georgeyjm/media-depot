import argparse
import sys
from pathlib import Path
from typing import Optional

import httpx
from tqdm import tqdm


DEFAULT_BASE_URL = 'http://localhost:8000'


def download_share(share: str, base_url: str = DEFAULT_BASE_URL, silent: bool = False) -> bool:
    '''
    Request download for a single share string.
    
    Args:
        share: The share string/URL to download
        base_url: Base URL of the API server
        silent: If True, suppress output messages
        
    Returns:
        True if successful, False otherwise
    '''
    if not share.strip():
        if not silent:
            print('Warning: Empty share string, skipping...', file=sys.stderr)
        return False
    
    url = f'{base_url}/download'
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json={'share': share})
            response.raise_for_status()
            if not silent:
                print(f'✓ Successfully requested download for: {share}')
            return True
    except httpx.HTTPStatusError as e:
        if not silent:
            print(f'✗ HTTP error for "{share}": {e.response.status_code} - {e.response.text}', file=sys.stderr)
        return False
    except httpx.RequestError as e:
        if not silent:
            print(f'✗ Request error for "{share}": {e}', file=sys.stderr)
        return False
    except Exception as e:
        if not silent:
            print(f'✗ Unexpected error for "{share}": {e}', file=sys.stderr)
        return False


def download_from_file(file_path: Path, base_url: str = DEFAULT_BASE_URL) -> None:
    '''
    Read share strings from a file and request download for each.
    Empty lines are skipped.
    
    Args:
        file_path: Path to the file containing share strings (one per line)
        base_url: Base URL of the API server
    '''
    if not file_path.exists():
        print(f'Error: File not found: {file_path}', file=sys.stderr)
        sys.exit(1)
    
    if not file_path.is_file():
        print(f'Error: Not a file: {file_path}', file=sys.stderr)
        sys.exit(1)
    
    print(f'Reading share strings from: {file_path}')
    
    # First pass: count non-empty lines
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            total_lines = sum(1 for line in f if line.strip())
    except Exception as e:
        print(f'Error reading file: {e}', file=sys.stderr)
        sys.exit(1)
    
    if total_lines == 0:
        print('No non-empty lines found in file.')
        return
    
    successful = 0
    failed = 0
    
    # Second pass: process lines with progress bar
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            with tqdm(total=total_lines, desc='Processing shares', unit='share') as pbar:
                for line_num, line in enumerate(f, start=1):
                    share = line.strip()
                    if share:  # Skip empty lines
                        pbar.set_description(f'Processing: {share[:50]}...' if len(share) > 50 else f'Processing: {share}')
                        if download_share(share, base_url, silent=True):
                            successful += 1
                            tqdm.write(f'✓ [{line_num}] Successfully requested download for: {share}')
                        else:
                            failed += 1
                            tqdm.write(f'✗ [{line_num}] Failed to request download for: {share}')
                        pbar.update(1)
                    else:
                        tqdm.write(f'[{line_num}] Skipping empty line')
    
    except Exception as e:
        print(f'Error reading file: {e}', file=sys.stderr)
        sys.exit(1)
    
    print(f'\n{'='*50}')
    print(f'Summary: {successful} successful, {failed} failed')
    print(f'{'='*50}')


def main():
    '''Main CLI entry point.'''
    parser = argparse.ArgumentParser(
        description='Media Depot CLI - Download media from share strings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Download from a single share string
  python cli.py --share 'https://www.bilibili.com/video/BV1234567890'
  
  # Download from a file containing share strings
  python cli.py --file shares.txt
  
  # Use a custom API server URL
  python cli.py --share 'https://...' --base-url 'http://localhost:9000'
        '''
    )
    
    parser.add_argument(
        '--share',
        type=str,
        help='Single share string/URL to download'
    )
    
    parser.add_argument(
        '--file',
        type=Path,
        help='Path to file containing share strings (one per line)'
    )
    
    parser.add_argument(
        '--base-url',
        type=str,
        default=DEFAULT_BASE_URL,
        help=f'Base URL of the API server (default: {DEFAULT_BASE_URL})'
    )
    
    args = parser.parse_args()
    
    # Validate that exactly one of --share or --file is provided
    if args.share and args.file:
        print('Error: Cannot specify both --share and --file', file=sys.stderr)
        sys.exit(1)
    
    if not args.share and not args.file:
        print('Error: Must specify either --share or --file', file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Execute the appropriate function
    if args.share:
        success = download_share(args.share, args.base_url)
        sys.exit(0 if success else 1)
    else:
        download_from_file(args.file, args.base_url)


if __name__ == '__main__':
    main()

