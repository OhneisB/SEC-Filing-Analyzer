from sec_filing_analyzer.edgar.rate_limiter import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_enforces_min_interval():
    fake = FakeClock()
    rl = RateLimiter(max_per_second=10, clock=fake.clock, sleep=fake.sleep)

    rl.acquire()  # first call: no wait
    assert fake.slept == []

    rl.acquire()  # immediate second call must wait ~0.1s
    assert len(fake.slept) == 1
    assert abs(fake.slept[0] - 0.1) < 1e-9


def test_no_wait_when_spaced_out():
    fake = FakeClock()
    rl = RateLimiter(max_per_second=10, clock=fake.clock, sleep=fake.sleep)
    rl.acquire()
    fake.now += 5.0  # plenty of time passed
    rl.acquire()
    assert fake.slept == []


def test_caps_at_sec_limit():
    rl = RateLimiter(max_per_second=100)
    assert rl.min_interval >= 0.1  # SEC cap: 10 req/s
