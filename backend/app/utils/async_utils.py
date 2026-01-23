""" Async utilities for running synchronous code in thread pool."""
import asyncio
from functools import partial
from typing import TypeVar, Callable, Any
from concurrent.futures import ThreadPoolExecutor

T = TypeVar('T')

_db_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="db_")


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
   
    loop = asyncio.get_event_loop()
    
    if kwargs:
        func_with_kwargs = partial(func, *args, **kwargs)
        return await loop.run_in_executor(_db_executor, func_with_kwargs)
    
    return await loop.run_in_executor(_db_executor, func, *args)


def shutdown_executor():
    _db_executor.shutdown(wait=True)