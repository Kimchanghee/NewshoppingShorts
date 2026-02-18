from ..DouyinExtract import download_tiktok_douyin_video


def download(url: str, max_retries: int = 3) -> str:
    return download_tiktok_douyin_video(url, max_retries=max_retries)
