from ..KuaishouExtract import download_kuaishou_video


def download(url: str, max_retries: int = 3) -> str:
    return download_kuaishou_video(url, max_retries=max_retries)
