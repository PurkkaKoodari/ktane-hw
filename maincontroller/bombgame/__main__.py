from asyncio import run
from logging import getLogger
from sys import argv

from bombgame.controller import BombGameController
from bombgame.logging import init_logging
from bombgame.utils import handle_sigint

LOGGER = getLogger("Main")


async def main():
    verbose = "-v" in argv
    init_logging(verbose)
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    quit_evt = handle_sigint()
    game = BombGameController()
    await game.start()
    await quit_evt.wait()
    await game.stop()
    LOGGER.info("Exiting")

if __name__ == "__main__":
    run(main())
