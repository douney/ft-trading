from enum import Enum

class TimeFrame(Enum):
    """Enum for different time frames."""

    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"

    def __str__(self):
        return self.value

    def from_string(cls, timeframe_str: str):
        """Convert a string to a TimeFrame enum."""
        try:
            return cls[timeframe_str.upper()]
        except KeyError:
            raise ValueError(f"Invalid timeframe: {timeframe_str}")
