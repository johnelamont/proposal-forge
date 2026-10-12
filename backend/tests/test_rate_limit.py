from app.services.rate_limit import RateLimiter


def test_sliding_window_per_key():
    rl = RateLimiter(limit=3, window_seconds=60)
    assert all(rl.allow("a", now=t) for t in (0, 1, 2))
    assert not rl.allow("a", now=3)  # fourth within the window
    assert rl.allow("b", now=3)  # other keys are independent
    assert rl.allow("a", now=61)  # the first hit has aged out
    rl.reset()
    assert rl.allow("a", now=62)
