import json
import time
from typing import Optional

from modules.broker.ig.ig_exception import *
from modules.broker.ig.services.ig_session import IGAction, IGSession

from ..utils.utils import parse_response

import logging
logger = logging.getLogger(__name__)


class IGDealing:
    def __init__(self, ig_session: IGSession):
        self.ig_session = ig_session

    def fetch_deal_by_deal_reference(self, deal_reference: str):
        """Returns a deal confirmation for the given deal reference"""
        version = "1"
        params: dict[str, str] = {}
        url_params = {"deal_reference": deal_reference}
        endpoint = "/confirms/{deal_reference}".format(**url_params)
        action = IGAction.READ

        response = self.ig_session.request(action, endpoint, params, version)
        if response.status_code == 200:
            data = parse_response(response.text)
            print(f"Deal: {data}")
            return data
        
        for _ in range(5):
            response = self.ig_session.request(action, endpoint, params, version)
            if not response.status_code == 200:
                logger.info("Deal reference %s not found, retrying." %
                            deal_reference)
                time.sleep(1)
            else:
                break

        data = parse_response(response.text)

        return data

    def fetch_open_position_by_deal_id(self, deal_id: str):
        """Return the open position by deal id for the active account"""
        version = "2"
        params: dict[str, str] = {}
        url_params = {"deal_id": deal_id}
        endpoint = "/positions/{deal_id}".format(**url_params)
        action = IGAction.READ

        response = self.ig_session.request(action, endpoint, params, version)
        if response.status_code == 200:
            return parse_response(response.text)
        
        for _ in range(5):
            response = self.ig_session.request(action, endpoint, params, version)
            if not response.status_code == 200:
                logger.info("Deal id %s not found, retrying." % deal_id)
                time.sleep(1)
            else:
                break

        data = parse_response(response.text)
        return data

    def fetch_open_positions(self, version: str = "2"):
        """
        Returns all open positions for the active account. Supports both v1 and v2
        :param session: session object, otional
        :type session: Session
        :param version: API version, 1 or 2
        :type version: str
        :return: table of position data, one per row
        :rtype: pd.Dataframe
        """
        params: dict[str, str] = {}
        endpoint = "/positions"
        action = IGAction.READ

        response = self.ig_session.request(action, endpoint, params, version)
        if response.status_code == 200:
            return parse_response(response.text)

        for _ in range(5):
            response = self.ig_session.request(action, endpoint, params, version)

            if not response.status_code == 200:
                logger.info("Error fetching open positions, retrying.")
                time.sleep(1)
            else:
                break

        data = parse_response(response.text)

        return data

    def close_open_position(
        self,
        deal_id: str,
        direction: str,
        expiry: str,
        validity_level: Optional[float],
        size: float
    ):
        """Closes one or more OTC positions"""
        # self.ig_session.trading_rate_limit_pause_or_pass()
        version = "1"
        params: dict[str, str] = {
            "dealId": deal_id,
            "direction": direction,
            "expiry": expiry,
            "orderType": "MARKET",
            "size": str(size),
        }

        if validity_level is not None:
            params["level"] = str(validity_level)
            params["orderType"] = "LIMIT"

        endpoint = "/positions/otc"
        action = IGAction.DELETE
        response = self.ig_session.request(action, endpoint, params, version)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)["dealReference"]
            deal = self.fetch_deal_by_deal_reference(deal_reference)
            if (deal["reason"] != "SUCCESS"):
                logger.error(json.dumps(deal, indent=4))
        else:
            raise IGException(response.text)

    def create_open_position(
        self,
        currency_code: str,
        direction: str,
        epic: str,
        stop_distance: Optional[float],
        size: float,
        limit_distance: Optional[float] = None,
        validity_level: Optional[float] = None,
    ):
        if (stop_distance is None):
            raise IGException("stop_distance is required")

        # self.ig_session.trading_rate_limit_pause_or_pass()
        version = "2"
        params: dict[str, str] = {
            "currencyCode": currency_code,
            "dealRefereence": "NEWORDER",
            "direction": direction,
            "epic": epic,
            "expiry": "-",
            "forceOpen": "true",
            "guaranteedStop": "true",
            "stopDistance": str(stop_distance),
            "size": str(size),
            "trailingStop": "false",
        }

        if validity_level is not None:
            params["orderType"] = "LIMIT"
            params["level"] = str(validity_level)
            params["timeInForce"] = "FILL_OR_KILL"
        else:
            params["orderType"] = "MARKET"

        if limit_distance is not None:
            params["limitDistance"] = str(limit_distance)

        endpoint = "/positions/otc"
        action = IGAction.CREATE

        response = self.ig_session.request(action, endpoint, params, version)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)["dealReference"]
            deal = self.fetch_deal_by_deal_reference(deal_reference)
            if (deal["reason"] != "SUCCESS"):
                logger.error(json.dumps(deal, indent=4))
        else:
            raise IGException(response.text)

    def update_open_position(
        self,
        deal_id: str,
        limit_level: Optional[float],
        stop_level: Optional[float],
        version: str = "2",
    ):
        """Updates an OTC position"""
        # self.ig_session.trading_rate_limit_pause_or_pass()
        params: dict[str, str] = {
            "guaranteedStop": "true",
            "stopLevel": str(stop_level),
            "trailingStop": "false",
        }

        if limit_level is not None:
            params["limitLevel"] = str(limit_level)

        print(f"Params: {params}")

        url_params = {"deal_id": deal_id}
        endpoint = "/positions/otc/{deal_id}".format(**url_params)
        action = IGAction.UPDATE
        response = self.ig_session.request(action, endpoint, params, version)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)["dealReference"]
            return self.fetch_deal_by_deal_reference(deal_reference)
        else:
            raise IGException(response.text)

    def fetch_working_orders(self, version: str = "2"):
        """Returns all open working orders for the active account"""
        # self.ig_session.non_trading_rate_limit_pause_or_pass() 
        params: dict[str, str] = {}
        endpoint = "/workingorders"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data