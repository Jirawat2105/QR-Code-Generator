"""Bounded background workers; processes on desktop, portable threads on Android."""
import asyncio
import atexit
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial

from .engine import Design, render

_pool = None


def is_android():
    return sys.platform == "android" or os.environ.get("FLET_PLATFORM")=="android" or hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ


def get_pool():
    global _pool
    if _pool is None:
        # Two simultaneous large image exports fit comfortably within typical RAM.
        count = min(4 if is_android() else 2, os.cpu_count() or 1)
        # Flutter's embedded desktop runtime has no child Python executable.
        embedded=os.environ.get("FLET_PLATFORM") is not None and not getattr(sys,"frozen",False)
        cls = ThreadPoolExecutor if is_android() or embedded or sys.platform in ("ios", "emscripten") else ProcessPoolExecutor
        _pool = cls(max_workers=count)
    return _pool


async def render_async(design: Design, fmt="PNG", preview_size=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_pool(), partial(render, design, fmt, preview_size))


def shutdown():
    global _pool
    if _pool:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None


atexit.register(shutdown)
