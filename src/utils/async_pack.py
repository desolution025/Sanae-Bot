from functools import partial
import asyncio
from concurrent.futures import ThreadPoolExecutor


thread_pool = ThreadPoolExecutor(max_workers=12)


async def async_exec(func, *arg, **kw):
    """异步包裹函数"""
    func = partial(func, **kw)
    return await asyncio.get_event_loop().run_in_executor(thread_pool, func, *arg) 