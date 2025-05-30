from typing import Optional, Callable
import math, time, asyncio
from contextlib import contextmanager, asynccontextmanager


class Timer:
    """Simple timer utility for measuring execution time"""
    
    def __init__(self, name: str = "Operation", precision: int = 4, callback: Optional[Callable] = None):
        self.name = name
        self.precision = precision
        self.callback = callback
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.elapsed: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time
        result = f"{self.name} took {self.elapsed:.{self.precision}f} seconds"
        
        if self.callback:
            self.callback(self.elapsed, result)
        else:
            print(result)
    
    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time
        result = f"{self.name} took {self.elapsed:.{self.precision}f} seconds"
        
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(self.elapsed, result)
            else:
                self.callback(self.elapsed, result)
        else:
            print(result)

@contextmanager
def time_it(name: str = "Operation", precision: int = 4, callback: Optional[Callable] = None):
    """Context manager for timing synchronous code execution"""
    timer = Timer(name, precision, callback)
    with timer:
        yield timer

@asynccontextmanager
async def atime_it(name: str = "Operation", precision: int = 4, callback: Optional[Callable] = None):
    """Async context manager for timing asynchronous code execution"""
    timer = Timer(name, precision, callback)
    async with timer:
        yield timer