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
