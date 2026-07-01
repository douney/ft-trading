import logging

from modules.manager.trading_manager import TradingManager


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    trading_manager = TradingManager()
    trading_manager.start()

    try:
        trading_manager.join()
    except KeyboardInterrupt:
        trading_manager.stop()
        trading_manager.join()


if __name__ == "__main__":
    main()
