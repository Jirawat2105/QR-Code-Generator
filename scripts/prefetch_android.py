"""Populate Flet's documented build cache when Gradle's network download times out."""
import concurrent.futures
import tarfile
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CACHE=Path.home()/".flet"/"cache"


def fetch(item):
    url,dest=item
    if dest.exists() and dest.stat().st_size>10000:
        return f"Cached {dest.name}"
    dest.parent.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    session.mount("https://",HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1)))
    print(f"Downloading {dest.name}",flush=True)
    with session.get(url,stream=True,timeout=(20,60)) as r:
        r.raise_for_status()
        temp=dest.with_suffix(dest.suffix+".partial")
        with temp.open("wb") as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)
        if dest.name.endswith(".tar.gz") and not tarfile.is_tarfile(temp):
            raise ValueError(f"Invalid runtime archive: {dest.name}")
        temp.replace(dest)
    return f"Downloaded {dest.name}: {dest.stat().st_size//1024//1024} MB"


if __name__=="__main__":
    items=[]
    for abi in ("arm64-v8a","x86_64","armeabi-v7a"):
        name=f"python-android-dart-3.13.18-{abi}.tar.gz"
        items.append((f"https://github.com/flet-dev/python-build/releases/download/20261027/{name}",CACHE/"python-build"/"v3.13.18"/name))
        name=f"libdart_bridge-android-{abi}-py3.13.so"
        items.append((f"https://github.com/flet-dev/dart-bridge/releases/download/v1.11.0/{name}",CACHE/"dart-bridge"/"v1.11.0"/name))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(fetch,items):
            print(result,flush=True)
