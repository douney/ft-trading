#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

import sys
import traceback
import logging

from lightstreamer.client import LightstreamerClient

from modules.broker.ig.services.ig_session import IGSession
from modules.broker.ig.subscription import BaseSubscription

logger = logging.getLogger(__name__)


class IGStream(object):
    def __init__(self, ig_session: IGSession, acc_number=None):
        self.ig_session = ig_session
        self.acc_number = acc_number
        self.lightstreamerEndpoint = None
        self.ls_client = None

    def connect(self, version="2"):
        # if we have created a v3 session, we also need the session tokens
        if version == "3":
            self.ig_session.read_session(fetch_session_tokens="true")

        self.lightstreamerEndpoint = self.ig_session.sessionResponse["lightstreamerEndpoint"]
        cst = self.ig_session.session.headers["CST"]
        xsecuritytoken = self.ig_session.session.headers["X-SECURITY-TOKEN"]
        ls_password = "CST-%s|XST-%s" % (cst, xsecuritytoken)

        # Establishing a new connection to Lightstreamer Server
        logger.info("Starting connection with %s" % self.lightstreamerEndpoint)
        self.ls_client = LightstreamerClient(self.lightstreamerEndpoint, None)
        self.ls_client.connectionDetails.setUser(self.acc_number)
        self.ls_client.connectionDetails.setPassword(ls_password)
        try:
            self.ls_client.connect()
            logger.info("Connected to Lightstreamer Server")
            return
        except Exception:
            logger.error("Unable to connect to Lightstreamer Server")
            logger.error(traceback.format_exc())
            sys.exit(1)

    def subscribe(self, subscription: BaseSubscription):
        self.ls_client.subscribe(subscription)
        return subscription

    def unsubscribe(self, subscription: BaseSubscription):
        self.ls_client.unsubscribe(subscription)

    def unsubscribe_all(self):
        # To avoid a RuntimeError: dictionary changed size during iteration
        subscriptions = self.ls_client.getSubscriptions().copy()
        for sub in subscriptions:
            self.ls_client.unsubscribe(sub)

    def disconnect(self):
        self.unsubscribe_all()
        self.ls_client.disconnect()
