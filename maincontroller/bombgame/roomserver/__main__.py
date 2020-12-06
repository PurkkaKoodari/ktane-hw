from asyncio import run
from logging import getLogger
from sys import argv

from bombgame.logging import init_logging
from bombgame.roomserver.server import RoomServer
from bombgame.utils import handle_sigint

LOGGER = getLogger("RoomServer")


async def main():
    verbose = "-v" in argv
    init_logging(verbose)
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    quit_evt = handle_sigint()
    server = RoomServer()
    await server.start()
    await quit_evt.wait()
    await server.stop()
    LOGGER.info("Exiting")

if __name__ == "__main__":
    run(main())
