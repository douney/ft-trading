
from modules.base_type.currency import Currency
from modules.base_type.position import PositionDirection, PositionStatus


class TypesConvertor:
    def __init__(self):
        pass

    @staticmethod
    def to_currency(currency: str) -> Currency:
        if currency == "GBP":
            return Currency.GBP
        elif currency == "USD":
            return Currency.USD
        elif currency == "EUR":
            return Currency.EUR
        else:
            raise ValueError(f"Unknown currency: {currency}")
        
    @staticmethod
    def from_currency(currency: Currency) -> str:
        if currency == Currency.GBP:
            return "GBP"
        elif currency == Currency.USD:
            return "USD"
        elif currency == Currency.EUR:
            return "EUR"
        else:
            raise ValueError(f"Unknown currency: {currency}")
        
    @staticmethod
    def to_position_status(status: str) -> PositionStatus:
        if status == "OPEN":
            return PositionStatus.OPEN
        elif status == "UPDATED":
            return PositionStatus.UPDATED
        elif status == "DELETED":
            return PositionStatus.DELETED
        else:
            raise ValueError(f"Unknown position status: {status}")
        
    @staticmethod
    def from_position_status(status: PositionStatus) -> str:
        if status == PositionStatus.OPEN:
            return "OPEN"
        elif status == PositionStatus.UPDATED:
            return "UPDATED"
        elif status == PositionStatus.DELETED:
            return "DELETED"
        else:
            raise ValueError(f"Unknown position status: {status}")
        
    @staticmethod
    def to_position_direction(direction: str) -> PositionDirection:
        if direction == "BUY":
            return PositionDirection.BUY
        elif direction == "SELL":
            return PositionDirection.SELL
        else:
            raise ValueError(f"Unknown position direction: {direction}")
        
    @staticmethod
    def from_position_direction(direction: PositionDirection) -> str:
        if direction == PositionDirection.BUY:
            return "BUY"
        elif direction == PositionDirection.SELL:
            return "SELL"
        else:
            raise ValueError(f"Unknown position direction: {direction}")