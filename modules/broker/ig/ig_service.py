import json
from typing import Optional

from modules.broker.ig.ig_exception import *
from modules.broker.ig.services.ig_session import IGSession
from modules.broker.ig.services.ig_account import IGAccount
from modules.broker.ig.services.ig_dealing import IGDealing
from modules.broker.ig.services.ig_general import IGGeneral
from modules.broker.ig.services.ig_market import IGMarket
from modules.broker.ig.services.ig_watchlists import IGWatchlists
from modules.broker.ig.services.ig_stream import IGStream

import logging
logger = logging.getLogger(__name__)


class IGService:
    D_BASE_URL = {
        "live": "https://api.ig.com/gateway/deal",
        "demo": "https://demo-api.ig.com/gateway/deal",
    }

    def __init__(
        self,
        username: str,
        api_key: str,
        acc_type: str = "demo",
        acc_number: Optional[str] = None
    ):
        """Constructor, calls the method required to connect to
        the API (accepts acc_type = LIVE or DEMO)"""

        try:
            baseUrl = self.D_BASE_URL[acc_type.lower()]
        except Exception:
            raise IGException(
                "Invalid account type '%s', please provide LIVE or DEMO" % acc_type
            )

        self.ig_session = IGSession(baseUrl, api_key, username, acc_number=acc_number)

        self.account = IGAccount(self.ig_session)
        self.market = IGMarket(self.ig_session)
        self.watchlists = IGWatchlists(self.ig_session)
        self.deal = IGDealing(self.ig_session)
        self.general = IGGeneral(self.ig_session)

        self.stream = IGStream(self.ig_session, acc_number=acc_number)

    def connect(self, password: str):
        resp = self.ig_session.create_session(password, False)
        logger.info(json.dumps(resp, indent=4, sort_keys=True))
