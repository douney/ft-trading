import logging

from modules.broker.ig.services.ig_session import IGSession

from ..utils.utils import parse_response, pd

logger = logging.getLogger(__name__)


class IGWatchlists:
    def __init__(self, ig_session: IGSession):
        self.ig_session = ig_session

    def fetch_all_watchlists(self):
        """Returns all watchlists belonging to the active account"""
        version = "1"
        params = {}
        endpoint = "/watchlists"
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def create_watchlist(self, name, epics):
        """Creates a watchlist"""
        version = "1"
        params = {"name": name, "epics": epics}
        endpoint = "/watchlists"
        action = IGAction.CREATE
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data

    def delete_watchlist(self, watchlist_id):
        """Deletes a watchlist"""
        version = "1"
        params = {}
        url_params = {"watchlist_id": watchlist_id}
        endpoint = "/watchlists/{watchlist_id}".format(**url_params)
        action = IGAction.DELETE
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data

    def fetch_watchlist_markets(self, watchlist_id):
        """Returns the given watchlist's markets"""
        version = "1"
        params = {}
        url_params = {"watchlist_id": watchlist_id}
        endpoint = "/watchlists/{watchlist_id}".format(**url_params)
        action = IGAction.READ
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)

        return data

    def add_market_to_watchlist(self, watchlist_id, epic):
        """Adds a market to a watchlist"""
        version = "1"
        params = {"epic": epic}
        url_params = {"watchlist_id": watchlist_id}
        endpoint = "/watchlists/{watchlist_id}".format(**url_params)
        action = IGAction.UPDATE
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data

    def remove_market_from_watchlist(self, watchlist_id, epic):
        """Remove a market from a watchlist"""
        version = "1"
        params = {}
        url_params = {"watchlist_id": watchlist_id, "epic": epic}
        endpoint = "/watchlists/{watchlist_id}/{epic}".format(**url_params)
        action = IGAction.DELETE
        response = self.ig_session.request(action, endpoint, params, version)
        data = parse_response(response.text)
        return data
