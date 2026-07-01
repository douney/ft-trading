from enum import Enum

class Currency(Enum):
    NONE = "NONE"
    GBP = "GBP"
    USD = "USD"
    EUR = "EUR"

    def __str__(self):
        return self.value