from dataclasses import dataclass

@dataclass
class Tick:
    bid: float
    ask: float
    timestamp_ms: int

    def get_price(self) -> float:
        return (self.bid + self.ask) / 2
