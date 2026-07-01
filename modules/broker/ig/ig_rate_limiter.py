class IGRateLimiter:
    """
    A class to handle rate limiting for IG API requests.
    """

    def __init__(self):
        pass

    def setup_rate_limiter(
        self,
    ):
        data = self.get_client_apps()
        for acc in data:
            if acc["apiKey"] == self.API_KEY:
                break

        # If self.create_session() is called a second time, we should exit any
        # currently running threads
        self._exit_bucket_threads()

        # Horrific magic number to reduce API published allowable requests per minute
        # to a value that wont result in
        # 403 -> error.public-api.exceeded-account-trading-allowance
        # Tested for non_trading = 30 (live) and 10 (demo) requests per minute.
        # This wouldn't be needed if IG's API functioned as published!
        MAGIC_NUMBER = 2

        self._trading_requests_per_minute = (
            acc["allowanceAccountTrading"] - MAGIC_NUMBER
        )
        logger.info(
            f"Published IG Trading Request limits for trading request: "
            f"{acc['allowanceAccountTrading']} per minute. "
            f"Using: {self._trading_requests_per_minute}"
        )

        self._non_trading_requests_per_minute = (
            acc["allowanceAccountOverall"] - MAGIC_NUMBER
        )
        logger.info(
            f"Published IG Trading Request limits for non-trading request: "
            f"{acc['allowanceAccountOverall']} per minute. "
            f"Using {self._non_trading_requests_per_minute}"
        )

        time.sleep(60.0 / self._non_trading_requests_per_minute)

        self._bucket_threads_run = True  # Thread exit variable

        # Create a leaky token bucket for trading requests
        trading_requests_burst = 1  # If IG ever allow bursting, increase this
        self._trading_requests_queue = Queue(trading_requests_burst)
        # prefill the bucket so we can burst
        [self._trading_requests_queue.put(True)
         for i in range(trading_requests_burst)]
        token_bucket_trading_thread = Thread(
            target=self._token_bucket_trading,
        )
        token_bucket_trading_thread.start()
        self._trading_times = []

        # Create a leaky token bucket for non-trading requests
        non_trading_requests_burst = 1  # If IG ever allow bursting, increase this
        self._non_trading_requests_queue = Queue(non_trading_requests_burst)
        # prefill the bucket so we can burst
        [
            self._non_trading_requests_queue.put(True)
            for i in range(non_trading_requests_burst)
        ]
        token_bucket_non_trading_thread = Thread(
            target=self._token_bucket_non_trading,
        )
        token_bucket_non_trading_thread.start()
        self._non_trading_times = []

        # TODO
        # Create a leaky token bucket for allowanceAccountHistoricalData
        return

    def _token_bucket_trading(
        self,
    ):
        while self._bucket_threads_run:
            time.sleep(60.0 / self._trading_requests_per_minute)
            self._trading_requests_queue.put(True, block=True)
        return

    def _token_bucket_non_trading(
        self,
    ):
        while self._bucket_threads_run:
            time.sleep(60.0 / self._non_trading_requests_per_minute)
            self._non_trading_requests_queue.put(True, block=True)
        return

    def trading_rate_limit_pause_or_pass(
        self,
    ):
        if self._use_rate_limiter:
            self._trading_requests_queue.get(block=True)
            self._trading_times.append(time.time())
            self._trading_times = [
                req_time
                for req_time in self._trading_times
                if req_time > time.time() - 60
            ]
            logger.info(
                f"Number of trading requests in last 60 seconds = "
                f"{len(self._trading_times)} of {self._trading_requests_per_minute}"
            )
        return

    def non_trading_rate_limit_pause_or_pass(
        self,
    ):
        if self._use_rate_limiter:
            self._non_trading_requests_queue.get(block=True)
            self._non_trading_times.append(time.time())
            self._non_trading_times = [
                req_time
                for req_time in self._non_trading_times
                if req_time > time.time() - 60
            ]
            logger.info(
                f"Number of non trading requests in last 60 seconds = "
                f"{len(self._non_trading_times)} of "
                f"{self._non_trading_requests_per_minute}"
            )
        return

    def _exit_bucket_threads(
        self,
    ):
        if self._use_rate_limiter:
            if self._bucket_threads_run:
                self._bucket_threads_run = False
                try:
                    self._trading_requests_queue.get(block=False)
                except Empty:
                    pass
                try:
                    self._non_trading_requests_queue.get(block=False)
                except Empty:
                    pass
        return
