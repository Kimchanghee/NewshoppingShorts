from ..XiaohongshuExtract import download_xiaohongshu_video


def download(url: str, max_retries: int = 3) -> str:
    return download_xiaohongshu_video(url, max_retries=max_retries)
