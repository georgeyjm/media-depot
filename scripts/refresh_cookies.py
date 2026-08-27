#!/usr/bin/env python3
'''
Refresh the cookie file from a local browser.

Run this ON THE HOST, not inside a container: browser cookie databases are
encrypted with a key stored in the OS keychain, which a container cannot reach.
The container reads the resulting file through the bind-mounted .cache directory,
so a refresh here takes effect immediately for the running worker.

It also syncs Douyin's cookies into the DouK-Downloader service, which keeps its
own cookie in services/douyin/Volume/settings.json rather than reading
cookies.txt. That service only loads the value at startup, so the container is
restarted when the cookie actually changes.

Usage:
    uv run scripts/refresh_cookies.py               # uses settings.COOKIES_FROM_BROWSER
    uv run scripts/refresh_cookies.py --browser chrome
    uv run scripts/refresh_cookies.py --check       # report freshness, extract nothing
    uv run scripts/refresh_cookies.py --skip-douyin # leave the Douyin service alone
    uv run scripts/refresh_cookies.py --no-restart  # write the cookie, don't restart
'''

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from http.cookiejar import MozillaCookieJar
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.utils.cookies import refresh_cookies_from_browser

DOUYIN_SETTINGS = PROJECT_ROOT / 'services' / 'douyin' / 'Volume' / 'settings.json'
DOUYIN_SERVICE = 'douyin-downloader'


def describe(cookie_file: Path) -> None:
    '''Print the current state of the cookie file.'''
    if not cookie_file.exists() or cookie_file.stat().st_size == 0:
        print(f'No cookie file at {cookie_file}')
        return
    age_hours = (time.time() - cookie_file.stat().st_mtime) / 3600
    with cookie_file.open() as f:
        count = sum(1 for line in f if line.strip() and not line.startswith('#'))
    stale = ' (STALE)' if age_hours * 3600 > settings.COOKIES_REFRESH_INTERVAL else ''
    print(f'{cookie_file}: {count} cookies, {age_hours:.1f}h old{stale}')


def cookie_string_for(cookie_file: Path, domain: str) -> str:
    '''Build a "k=v; k=v" Cookie header value from one domain's cookies.'''
    if not cookie_file.exists():
        return ''
    jar = MozillaCookieJar()
    jar.load(str(cookie_file), ignore_discard=True, ignore_expires=True)
    pairs = {}
    for cookie in jar:
        host = cookie.domain.lstrip('.')
        if host == domain or host.endswith('.' + domain):
            pairs[cookie.name] = cookie.value or ''
    return '; '.join(f'{k}={v}' for k, v in sorted(pairs.items()))


def write_json_atomic(path: Path, data: dict) -> None:
    """
    Write JSON via a temp file + rename, so a concurrent reader never sees a
    partially written file. DouK reads this file at startup.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.settings-', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        pathlib_tmp = Path(tmp)
        if pathlib_tmp.exists():
            pathlib_tmp.unlink()
        raise


def read_douyin_cookie() -> str:
    """Read the cookie currently stored in the Douyin settings file."""
    if not DOUYIN_SETTINGS.exists():
        return ''
    try:
        return json.loads(DOUYIN_SETTINGS.read_text(encoding='utf-8')).get('cookie', '')
    except json.JSONDecodeError:
        return ''


def sync_douyin_cookie(cookie_file: Path, restart: bool) -> None:
    '''
    Copy douyin.com cookies into the DouK-Downloader settings file.

    That service keeps its cookie in its own settings.json (as a "k=v; k=v"
    string) and only reads it at startup, so it needs a restart to pick up a
    change. Restarting only when the value actually changed keeps an hourly
    refresh from interrupting in-flight downloads.
    '''
    cookie = cookie_string_for(cookie_file, 'douyin.com')
    if not cookie:
        print('Skipping Douyin sync: no douyin.com cookies in the browser')
        return

    # The settings file may not exist yet if this runs before setup_douyin.sh.
    # Create it rather than skipping, so the two scripts can run in either order:
    # setup_douyin.sh merges into whatever is here and preserves the cookie.
    if not DOUYIN_SETTINGS.exists():
        write_json_atomic(DOUYIN_SETTINGS, {})
        print(f'Created {DOUYIN_SETTINGS} (run scripts/setup_douyin.sh to finish setup)')

    try:
        data = json.loads(DOUYIN_SETTINGS.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        print(f'Skipping Douyin sync: {DOUYIN_SETTINGS} is not valid JSON')
        return

    names = [pair.split('=', 1)[0] for pair in cookie.split('; ')]
    if data.get('cookie') == cookie:
        print(f'Douyin cookie unchanged ({len(names)} cookies); not restarting')
        return

    data['cookie'] = cookie
    write_json_atomic(DOUYIN_SETTINGS, data)
    print(f'Douyin cookie updated ({len(names)}): {", ".join(names)}')
    if 'sessionid' not in names:
        print('  Note: no sessionid - the browser is not logged in to Douyin. '
              'Anonymous cookies may still work for public posts.')

    if not restart:
        print('  Not restarting; run: docker compose restart ' + DOUYIN_SERVICE)
        return

    running = subprocess.run(
        ['docker', 'compose', 'ps', '-q', DOUYIN_SERVICE],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    if running.returncode != 0 or not running.stdout.strip():
        print('  Service is not running; it will pick up the new cookie on next start')
        return

    print(f'  Restarting {DOUYIN_SERVICE} to load it ...')
    restarted = subprocess.run(
        ['docker', 'compose', 'restart', DOUYIN_SERVICE],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    if restarted.returncode != 0:
        print(f'  Restart failed: {restarted.stderr.strip()[:200]}')
        return

    # DouK rewrites settings.json at startup when keys are missing (read, merge
    # defaults, write). If it read the file just before we wrote it, its write
    # puts the old cookie back. That only happens on a first run, but it fails
    # silently, so confirm the cookie survived and redo it once if not.
    time.sleep(6)
    if read_douyin_cookie() == cookie:
        print('  Restarted; cookie confirmed in place.')
        return

    print('  The service rewrote settings.json on startup; reapplying ...')
    try:
        data = json.loads(DOUYIN_SETTINGS.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        data = {}
    data['cookie'] = cookie
    write_json_atomic(DOUYIN_SETTINGS, data)
    subprocess.run(['docker', 'compose', 'restart', DOUYIN_SERVICE],
                   cwd=PROJECT_ROOT, capture_output=True, text=True)
    time.sleep(6)
    print('  Cookie confirmed in place.' if read_douyin_cookie() == cookie
          else '  WARNING: cookie still not applied - check '
               f'{DOUYIN_SETTINGS} and the service logs.')


def main() -> int:
    parser = argparse.ArgumentParser(description='Refresh cookies from a local browser.')
    parser.add_argument(
        '--browser',
        default=settings.COOKIES_FROM_BROWSER or 'edge',
        help='Browser to extract from (edge, chrome, firefox, safari, brave, opera, vivaldi)',
    )
    parser.add_argument('--check', action='store_true', help='Only report the current cookie file state')
    parser.add_argument('--skip-douyin', action='store_true', help='Do not touch the Douyin service settings')
    parser.add_argument('--no-restart', action='store_true', help='Write the Douyin cookie but do not restart it')
    args = parser.parse_args()

    cookie_file = settings.cookies_file

    if args.check:
        describe(cookie_file)
        if DOUYIN_SETTINGS.exists():
            try:
                current = json.loads(DOUYIN_SETTINGS.read_text(encoding='utf-8')).get('cookie', '')
            except json.JSONDecodeError:
                current = ''
            browser_side = cookie_string_for(cookie_file, 'douyin.com')
            state = 'in sync' if current == browser_side and current else (
                'not set' if not current else 'OUT OF SYNC with cookies.txt')
            print(f'{DOUYIN_SETTINGS.name}: douyin cookie {state}')
        return 0

    print(f'Extracting cookies from {args.browser} into {cookie_file} ...')
    if not refresh_cookies_from_browser(browser=args.browser, cookie_file=cookie_file):
        print(
            f'Failed to extract cookies from {args.browser}.\n'
            f'Make sure the browser is installed and, on macOS, grant your terminal '
            f'access when prompted for the keychain.',
            file=sys.stderr,
        )
        return 1

    describe(cookie_file)
    if not args.skip_douyin:
        sync_douyin_cookie(cookie_file, restart=not args.no_restart)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
