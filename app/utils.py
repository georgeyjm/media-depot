import re
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup


STREAM_FORMATS = ('h265', 'h264', 'av1')

url_re = re.compile(r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)')


def extract_url(text):
    match = url_re.search(text)
    if match is None:
        return
    url = match.group()

    if 'douyin.com' in url:
        return url
    elif 'xhslink.com' in url or 'xiaohongshu.com' in url:
        return url


def xhs_get_all_media(url, mode='download'):
    assert mode in ('download', 'url')

    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    # soup = BeautifulSoup(resp.text)
    # script = soup.find('script', string=re.compile(r'window\.__INITIAL_STATE__'))
    # test = re.split(r'=', script.string)
    # string = test[1].replace('undefined', 'null')
    # result = json.loads(string, strict=False)
    # image_list = result.get('note', {}).get('note', {}).get('imageList')

    match = re.search(r'window\.__INITIAL_STATE__=(.+)<\/script>', resp.text)
    if match is None:
        return
    json_str = match.groups()[0].replace('undefined', 'null')
    json_data = json.loads(json_str)
    note_data = list(json_data['note']['noteDetailMap'].values())[0]['note']
    
    if (video_data := note_data.get('video')):
        if mode == 'download':
            xhs_download_video(video_data, mode)
        elif mode == 'url':
            pass
    else:
        if mode == 'download':
            xhs_download_images(note_data['imageList'], mode)
        elif mode == 'url':
            pass


def xhs_download_video(video_data, mode):
    for format in STREAM_FORMATS:
        if (original_key := video_data.get('consumer', {}).get('originVideoKey')):
            # No watermark
            video_url = 'https://sns-video-hw.xhscdn.com/' + original_key # Regions: qc, hw (.com/.net), bd, qn
        else:
            # With watermark
            if not (stream_data := video_data['media']['stream'].get(format)):
                continue
            video_url = stream_data[0]['masterUrl']
        print(video_url)
    else:
        raise


def xhs_download_images(image_list, mode):
    for image in image_list:
        image_url = image.get('urlDefault')
        if not image['livePhoto']:
            pass # Download image only

        for format in STREAM_FORMATS:
            if not (stream_data := image['stream'].get(format)):
                continue
            video_url = stream_data[0]['masterUrl']
            # backup_urls = stream_data[0]['backupUrls']
            print(video_url, 'live')
            break
        else:
            raise


def download_media(url, filename=None, large=False):
    if filename is None:
        url_parsed = urlparse(url)
        filename = unquote(Path(url_parsed.path).name)
    elif isinstance(filename, str):
        filename = Path(filename) # Can also add root directory here

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with filename.open('wb') as f:
            shutil.copyfileobj(r.raw, f)
    # Deprecated method
    # with requests.get(url, stream=True) as r:
    #     r.raise_for_status()
    #     with filename.open('wb') as f:
    #         for chunk in r.iter_content(chunk_size=8192): 
    #             # If you have chunk encoded response uncomment if
    #             # and set chunk_size parameter to None.
    #             #if chunk: 
    #             f.write(chunk)
    
    return filename





share_text = '94 蓉么么发布了一篇小红书笔记，快来看吧！ 😆 9lelbSgbZ3gvE6u 😆 http://xhslink.com/GhryZT，复制本条信息，打开【小红书】App查看精彩内容！'
share_text = '6 九九御_发布了一篇小红书笔记，快来看吧！ 😆 czAhOA3NJckv2Xl 😆 http://xhslink.com/nDOAaU，复制本条信息，打开【小红书】App查看精彩内容！'
share_text = '63 LENG发布了一篇小红书笔记，快来看吧！ 😆 6HHYZxmNycLhjOo 😆 http://xhslink.com/puRCaU，复制本条信息，打开【小红书】App查看精彩内容！'
share_text = '48 Leah发布了一篇小红书笔记，快来看吧！ 😆 wOSHYiWqDEAZpvU 😆 http://xhslink.com/a/s4w2I4LVqcvZ，复制本条信息，打开【小红书】App查看精彩内容！'



{'livePhoto': False, 'height': 2560, 'url': '', 'traceId': '', 'infoList': [{'imageScene': 'WB_PRV', 'url': 'http://sns-webpic-qc.xhscdn.com/202408201829/398bc406cea89928fea5a9457b972c99/1040g2sg316m7r4ds3i7049vjm4vctnfkmtu2gt0!nd_prv_wlteh_jpg_3'}, {'imageScene': 'WB_DFT', 'url': 'http://sns-webpic-qc.xhscdn.com/202408201829/7ed714b96d3c19371ac98b6af134e01b/1040g2sg316m7r4ds3i7049vjm4vctnfkmtu2gt0!nd_dft_wlteh_jpg_3'}], 'urlPre': 'http://sns-webpic-qc.xhscdn.com/202408201829/398bc406cea89928fea5a9457b972c99/1040g2sg316m7r4ds3i7049vjm4vctnfkmtu2gt0!nd_prv_wlteh_jpg_3', 'fileId': '', 'width': 1920, 'urlDefault': 'http://sns-webpic-qc.xhscdn.com/202408201829/7ed714b96d3c19371ac98b6af134e01b/1040g2sg316m7r4ds3i7049vjm4vctnfkmtu2gt0!nd_dft_wlteh_jpg_3', 'stream': {}}
