from abc import ABC, abstractmethod

from lightstreamer.client import Subscription

import logging

from modules.base_type.queue_data import QueueData
logger = logging.getLogger(__name__)


class BaseSubscription(Subscription, ABC):
    @property
    @abstractmethod
    def TICKER_FIELDS(cls):
        """Child classes must define 'TICKER_FIELDS'."""
        pass

    @property
    @abstractmethod
    def MODE(cls):
        """Child classes must define 'MODE'."""
        pass

    def __init__(self, item: QueueData):
        logger.debug(f"Creating subscription for item: {item}")
        logger.debug(f"Fields: {self.TICKER_FIELDS}")
        logger.debug(f"Mode: {self.MODE}")

        super().__init__(
            mode=self.MODE,
            items=[item],
            fields=self.TICKER_FIELDS,
        )


class TickSubscription(BaseSubscription):
    TICKER_FIELDS = [
        "BID",
        "OFR",
        # "LTP",
        # "LTV",
        # "TTV",
        "UTM",
        # "DAY_OPEN_MID",
        # "DAY_NET_CHG_MID",
        # "DAY_PERC_CHG_MID",
        # "DAY_HIGH",
        # "DAY_LOW",
    ]

    MODE = "DISTINCT"

    def __init__(self, epic: str):
        super().__init__(item=f"CHART:{epic}:TICK")

class PositionSubscription(BaseSubscription):
    TICKER_FIELDS = [
        "CONFIRMS",
        "OPU",
        "WOU",
    ]

    MODE = "DISTINCT"

    def __init__(self, accound_id: str):
        super().__init__(item=f"TRADE:{accound_id}")