import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from tqdm import tqdm


API_ROOT_URL = 'http://localhost:8000/api'


# ============================================================================
# Helper Functions for API Requests
# ============================================================================

def request_download_job(share: str) -> dict:
    '''
    Request a download job from the API.
    
    Args:
        share: The share string/URL to download
        
    Returns:
        dict: Response data with 'job_id' and 'status' on success
        
    Raises:
        httpx.HTTPStatusError: If the HTTP request fails
        httpx.RequestError: If the request fails
    '''
    url = f'{API_ROOT_URL}/download'
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json={'share': share})
        response.raise_for_status()
        return response.json()


def poll_job_status(job_id: int) -> dict:
    '''
    Poll the status of a job from the API.
    
    Args:
        job_id: The job ID to poll
        
    Returns:
        dict: Job status data
        
    Raises:
        httpx.HTTPStatusError: If the HTTP request fails
        httpx.RequestError: If the request fails
    '''
    url = f'{API_ROOT_URL}/download/{job_id}'
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


# ============================================================================
# Helper Functions for File Operations
# ============================================================================

def load_or_convert_jobs_file(input_file: Path) -> tuple[list[dict], Path]:
    '''
    Load jobs from a JSON file or convert a text file to JSON.
    
    Args:
        input_file: Path to the input file (can be text or JSON)
        root_url: Base URL of the API server
        
    Returns:
        tuple: (jobs list, json_file path)
    '''
    if not input_file.exists():
        print(f'Error: Input file not found: {input_file}', file=sys.stderr)
        sys.exit(1)
    
    if not input_file.is_file():
        print(f'Error: Not a file: {input_file}', file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            # Try to parse as JSON
            try:
                jobs = json.load(f)
                if not isinstance(jobs, list):
                    raise ValueError('JSON file must contain a list of jobs')
                print(f'✓ Loaded {len(jobs)} jobs from JSON file: {input_file}')
                return jobs, input_file
            except json.JSONDecodeError:
                # Not JSON, convert it
                json_file = input_file.parent / f'{input_file.stem}.json'
                
                # Check if JSON file already exists
                if json_file.exists():
                    print(f'\n⚠ JSON file already exists: {json_file}')
                    while True:
                        response = input('Use existing JSON file? (y/n): ').strip().lower()
                        if response in ('y', 'yes'):
                            # Use existing JSON file
                            print(f'Using existing JSON file: {json_file}')
                            with open(json_file, 'r', encoding='utf-8') as jf:
                                jobs = json.load(jf)
                            if not isinstance(jobs, list):
                                raise ValueError('JSON file must contain a list of jobs')
                            print(f'✓ Loaded {len(jobs)} jobs from existing JSON file')
                            return jobs, json_file
                        elif response in ('n', 'no'):
                            # Overwrite with new conversion
                            print(f'Converting input file to JSON format (overwriting {json_file})...')
                            process_shares_to_json(input_file, json_file)
                            with open(json_file, 'r', encoding='utf-8') as jf:
                                jobs = json.load(jf)
                            return jobs, json_file
                        else:
                            print('Please enter "y" or "n"')
                
                # JSON file doesn't exist, convert normally
                print(f'Converting input file to JSON format...')
                process_shares_to_json(input_file, json_file)
                with open(json_file, 'r', encoding='utf-8') as jf:
                    jobs = json.load(jf)
                return jobs, json_file
    except Exception as e:
        print(f'Error reading input file: {e}', file=sys.stderr)
        sys.exit(1)


def save_jobs_to_file(jobs: list[dict], json_file: Path) -> None:
    '''
    Save jobs to a JSON file.
    
    Args:
        jobs: List of job dictionaries
        json_file: Path to the JSON file to save
    '''
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        print(f'\n💾 Progress saved to: {json_file}')
    except Exception as e:
        print(f'\n⚠ Error saving progress: {e}', file=sys.stderr)


# ============================================================================
# Helper Functions for Queue Management
# ============================================================================

def poll_all_jobs(
    active_queue: list[tuple[int, int, str]],
    jobs: list[dict],
) -> list[tuple[int, int, str]]:
    '''
    Poll status of all jobs in the active queue.
    
    Args:
        active_queue: List of (job_index, job_id, share) tuples
        jobs: List of all job dictionaries to update
        
    Returns:
        List of queue items that are completed/failed/canceled and should be removed
    '''
    jobs_to_remove = []
    
    for queue_item in active_queue:
        job_idx, job_id, share = queue_item
        try:
            job_data = poll_job_status(job_id)
            api_status = job_data.get('status', 'pending')
            
            # If API returns 'pending', keep it as 'processing' since it's in our active queue
            # Otherwise, use the API status (completed, failed, etc.)
            if api_status == 'pending':
                status = 'processing'
            else:
                status = api_status
            
            # Update job in the jobs list
            if job_idx < len(jobs):
                jobs[job_idx]['status'] = status
                jobs[job_idx]['data'] = job_data
            
            if status in ('completed', 'failed', 'canceled'):
                jobs_to_remove.append(queue_item)
                share_display = share[:50] + '...' if len(share) > 50 else share
                if status == 'completed':
                    tqdm.write(f'✓ Job {job_id} completed: {share_display}')
                else:
                    tqdm.write(f'✗ Job {job_id} {status}: {share_display}')
        except Exception:
            # Continue polling other jobs even if one fails
            continue
    
    return jobs_to_remove


def submit_job_to_queue(
    job: dict,
    job_index: int,
) -> tuple[Optional[int], Optional[dict]]:
    '''
    Submit a job to the download queue.
    
    Args:
        job: Job dictionary with 'share' field
        job_index: Index of the job in the jobs list
        
    Returns:
        tuple: (job_id, response_data) on success, (None, error_data) on failure
    '''
    share = job.get('share', '')
    if not share:
        return None, None
    
    try:
        response_data = request_download_job(share)
        job_id = response_data.get('job_id')
        
        if job_id:
            share_display = share[:50] + '...' if len(share) > 50 else share
            tqdm.write(f'→ Queued job {job_id}: {share_display}')
            return job_id, response_data
        else:
            error_data = {'error': 'No job_id in response', 'response': response_data}
            tqdm.write(f'✗ Failed to get job_id for: {share}')
            return None, error_data
            
    except httpx.HTTPStatusError as e:
        error_data = {
            'error': f'HTTP {e.response.status_code}',
            'message': e.response.text
        }
        tqdm.write(f'✗ HTTP error for "{share}": {e.response.status_code}')
        return None, error_data
        
    except httpx.RequestError as e:
        error_data = {
            'error': 'Request error',
            'message': str(e)
        }
        tqdm.write(f'✗ Request error for "{share}": {e}')
        return None, error_data
        
    except Exception as e:
        error_data = {
            'error': 'Unexpected error',
            'message': str(e)
        }
        tqdm.write(f'✗ Unexpected error for "{share}": {e}')
        return None, error_data


def calculate_job_statistics(jobs: list[dict], active_queue: list) -> dict[str, int]:
    '''
    Calculate statistics about job processing.
    
    Args:
        jobs: List of all job dictionaries
        active_queue: List of active jobs in queue
        
    Returns:
        Dictionary with 'completed', 'failed', 'pending', 'processing', 'in_queue' counts
    '''
    return {
        'completed': sum(1 for job in jobs if job.get('status') == 'completed'),
        'failed': sum(1 for job in jobs if job.get('status') in ('failed', 'error', 'canceled')),
        'pending': sum(1 for job in jobs if job.get('status') == 'pending'),
        'processing': sum(1 for job in jobs if job.get('status') == 'processing'),
        'in_queue': len(active_queue)
    }


# ============================================================================
# Main Functions
# ============================================================================

def download_share(share: str, silent: bool = False) -> bool:
    '''
    Request download for a single share string.
    
    Args:
        share: The share string/URL to download
        silent: If True, suppress output messages
        
    Returns:
        True if successful, False otherwise
    '''
    if not share.strip():
        if not silent:
            print('Warning: Empty share string, skipping...', file=sys.stderr)
        return False
    
    try:
        response_data = request_download_job(share)
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


def process_shares_to_json(input_file: Path, output_file: Path) -> None:
    '''
    Process an input file containing shares and generate a JSON file with job objects.
    
    Each line in the input file might be a share URL. If the next line is "good",
    then crawl_creator is set to True (False otherwise).
    
    Args:
        input_file: Path to the input file containing share strings
        output_file: Path to the output JSON file
    '''
    if not input_file.exists():
        print(f'Error: Input file not found: {input_file}', file=sys.stderr)
        sys.exit(1)
    if not input_file.is_file():
        print(f'Error: Not a file: {input_file}', file=sys.stderr)
        sys.exit(1)
    
    print(f'Reading shares from: {input_file}')
    
    # Read all lines from the input file and filter out empty lines
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = list(filter(lambda line: line.strip(), f))
    except Exception as e:
        print(f'Error reading input file: {e}', file=sys.stderr)
        sys.exit(1)
    
    jobs = []
    # Process lines: each line might be a share, next line might be "good"
    i = 0
    while i < len(lines):
        # Skip empty lines
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # Skip "good" lines (they should only appear after a share)
        if line.lower() == 'good':
            i += 1
            continue
        # Check if next line is "good"
        crawl_creator = False
        if i + 1 < len(lines) and lines[i + 1].strip().lower() == 'good':
            crawl_creator = True
            i += 1
        
        job = {
            'share': line,
            'crawl_creator': crawl_creator,
            'status': 'pending',
            'data': None,
        }
        jobs.append(job)
        i += 1
    
    # Write jobs to output JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        print(f'\n✓ Successfully wrote {len(jobs)} jobs to: {output_file}')
    except Exception as e:
        print(f'Error writing output file: {e}', file=sys.stderr)
        sys.exit(1)
    return output_file


def batch_download_from_file(
    input_file: Path,
    queue_size: int = 15,
    poll_interval: float = 2.0,
    wait: bool = True,
) -> None:
    '''
    Batch download from a file with optional queue management and polling.
    
    First converts the file to JSON if needed. If wait=True, processes jobs with a queue
    of size n, requests the API for each job and adds it to the queue. Every X seconds,
    polls /download/<job_id> to check if the job is completed. If wait=False, simply
    submits all unprocessed jobs to the API server and exits.
    
    Args:
        input_file: Path to the input file (can be text or JSON)
        queue_size: Maximum number of concurrent jobs in the queue (only used if wait=True)
        poll_interval: Interval in seconds between polling job status (only used if wait=True)
        wait: If True, manage queue and poll for completion. If False, just submit all jobs and exit.
    '''
    # Load or convert jobs file
    jobs, json_file = load_or_convert_jobs_file(input_file)
    
    if not jobs:
        print('No jobs to process.')
        return
    
    # If wait=False, just submit all unprocessed jobs and exit
    if not wait:
        print(f'Submitting all unprocessed jobs to API server (no queue management)...')
        submitted = 0
        skipped = 0
        failed = 0
        
        with tqdm(total=len(jobs), desc='Submitting jobs', unit='job') as pbar:
            for job_index, job in enumerate(jobs):
                # Skip empty shares
                if not job.get('share'):
                    skipped += 1
                    pbar.update(1)
                    continue
                
                # Skip if already completed or failed
                job_status = job.get('status', 'pending')
                if job_status in ('completed', 'failed', 'error', 'canceled'):
                    skipped += 1
                    pbar.update(1)
                    continue
                
                # Skip if already has a job_id (already submitted)
                if job.get('data') and job['data'].get('job_id'):
                    skipped += 1
                    pbar.update(1)
                    continue
                
                # Submit job to API
                job_id, response_data = submit_job_to_queue(job, job_index)
                
                if job_id:
                    jobs[job_index]['status'] = 'processing'
                    jobs[job_index]['data'] = response_data
                    submitted += 1
                else:
                    jobs[job_index]['status'] = 'error'
                    jobs[job_index]['data'] = response_data or {'error': 'Unknown error'}
                    failed += 1
                
                pbar.update(1)
        
        # Save progress
        save_jobs_to_file(jobs, json_file)
        
        # Print summary
        print(f'\n{'='*50}')
        print(f'Summary: {submitted} submitted, {failed} failed, {skipped} skipped')
        print(f'{'='*50}')
        return
    
    # wait=True: Use queue management and polling
    print(f'Processing {len(jobs)} jobs with queue size {queue_size} and poll interval {poll_interval}s')
    print('Press Ctrl+C at any time to stop and save progress.')
    
    # Initialize queue and tracking variables
    active_queue: list[tuple[int, int, str]] = []
    job_index = 0
    last_poll_time = time.time()
    interrupted = False
    
    try:
        with tqdm(total=len(jobs), desc='Processing jobs', unit='job') as pbar:
            while job_index < len(jobs) or active_queue:
                current_time = time.time()
                
                # Poll job statuses if enough time has passed
                if current_time - last_poll_time >= poll_interval:
                    jobs_to_remove = poll_all_jobs(active_queue, jobs)
                    
                    # Remove completed jobs from queue
                    for queue_item in jobs_to_remove:
                        active_queue.remove(queue_item)
                        pbar.update(1)
                    
                    last_poll_time = current_time
                
                # Add jobs to queue if there's space
                while job_index < len(jobs) and len(active_queue) < queue_size:
                    job = jobs[job_index]
                    
                    # Skip empty shares
                    if not job.get('share'):
                        job_index += 1
                        pbar.update(1)
                        continue
                    
                    # Skip if already completed or failed
                    job_status = job.get('status', 'pending')
                    if job_status in ('completed', 'failed', 'error', 'canceled'):
                        job_index += 1
                        pbar.update(1)
                        continue
                    
                    # If job has a job_id but status is still pending/processing, 
                    # add it back to the queue to monitor it
                    if job.get('data') and job['data'].get('job_id'):
                        job_id = job['data']['job_id']
                        if job_status in ('pending', 'processing'):
                            # Re-add to queue for monitoring
                            active_queue.append((job_index, job_id, job['share']))
                            if job_status == 'pending':
                                jobs[job_index]['status'] = 'processing'
                            job_index += 1
                            continue
                    
                    # Submit job to queue
                    job_id, response_data = submit_job_to_queue(job, job_index)
                    
                    if job_id:
                        # Successfully queued
                        active_queue.append((job_index, job_id, job['share']))
                        jobs[job_index]['status'] = 'processing'
                        jobs[job_index]['data'] = response_data
                        job_index += 1
                    else:
                        # Failed to submit
                        jobs[job_index]['status'] = 'error'
                        jobs[job_index]['data'] = response_data or {'error': 'Unknown error'}
                        pbar.update(1)
                        job_index += 1
                
                # Small sleep to avoid busy waiting
                if job_index < len(jobs) or active_queue:
                    time.sleep(0.1)
    
    except KeyboardInterrupt:
        interrupted = True
        print('\n\n⚠ Interrupted by user (Ctrl+C)', file=sys.stderr)
    
    # Save progress on exit (normal or interrupted)
    save_jobs_to_file(jobs, json_file)
    
    # Print summary
    stats = calculate_job_statistics(jobs, active_queue)
    print(f'\n{'='*50}')
    if interrupted:
        print(f'⚠ Process interrupted by user')
    print(f'Summary: {stats["completed"]} completed, {stats["failed"]} failed, '
          f'{stats["processing"]} processing, {stats["pending"]} pending, {stats["in_queue"]} still in queue')
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
        default=API_ROOT_URL,
        help=f'Base URL of the API server (default: {API_ROOT_URL})'
    )
    
    parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Submit all jobs to API and exit immediately (no queue management or polling)'
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
        success = download_share(args.share)
        sys.exit(0 if success else 1)
    else:
        batch_download_from_file(args.file, wait=not args.no_wait)


if __name__ == '__main__':
    main()
