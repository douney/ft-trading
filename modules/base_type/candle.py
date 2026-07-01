from modules.base_type.tick import Tick

class Candle:
    def __init__(self, resolution_min: int, timestamp: int):
        self.resolution_min = resolution_min
        self.timestamp = timestamp
        self.open = None
        self.close = None
        self.high = None
        self.low = None

    def add_tick(self, tick: Tick):
        if self.open is None:
            self.open = tick.bid
        self.close = tick.bid
        if self.high is None or tick.bid > self.high:
            self.high = tick.bid
        if self.low is None or tick.bid < self.low:
            self.low = tick.bid

    def __str__(self):
        return f"Candle(open={self.open}, close={self.close}, high={self.high}, low={self.low}, timestamp={self.timestamp})"
