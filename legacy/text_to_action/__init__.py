import functools

def helper(func):
    """
    A decorator to mark helper functions.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # print(f"Calling helper function: {func.__name__}")
        return func(*args, **kwargs)
    return wrapper