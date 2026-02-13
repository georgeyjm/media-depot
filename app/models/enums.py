from enum import StrEnum


class PostType(StrEnum):
    video = 'video'
    carousel = 'carousel'
    unknown = 'unknown'


class MediaType(StrEnum):
    image = 'image'
    video = 'video'
    live_photo = 'live_photo'
    live_video = 'live_video'
    profile_pic = 'profile_pic'
    thumbnail = 'thumbnail'
    unknown = 'unknown'


class JobStatus(StrEnum):
    pending = 'pending'
    processing = 'processing'
    completed = 'completed'
    failed = 'failed'
    canceled = 'canceled'


# class ScrapeMethod(StrEnum):
#     api = 'api'
#     html = 'html'
#     headless = 'headless'
#     hybrid = 'hybrid'


# class ScrapeStatus(StrEnum):
#     success = 'success'
#     failed = 'failed'
#     partial = 'partial'


class UserAgent(StrEnum):
    WINDOWS_CHROME = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    MAC_EDGE = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0'
    IOS_SAFARI = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1 Edg/143.0.0.0'
    WECHAT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.67(0x1800432e) NetType/WIFI Language/zh_CN'
