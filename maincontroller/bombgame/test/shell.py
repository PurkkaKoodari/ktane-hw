"""Provides a way to run the game with a virtual bomb and interact with it from the asyncio shell.

Usage:

1. Start the asyncio shell by typing ``python -m asyncio`` (requires Python 3.8+).
2. Import the shell: ``from bombgame.test.shell import main``
3. Run the game and get variables to interact with it: ``locals().update(main())``
4. Interact with the virtual bomb from the shell
5. Kill the game task and exit the shell by pressing Ctrl-C
"""

from __future__ import annotations

from asyncio import create_task, get_running_loop
from logging import getLogger

from bombgame.bus.bus import BombBus
from bombgame.controller import init_game, init_logging, run_game, handle_fatal_error, handle_sigint
from bombgame.test.mock import MockGpio, MockPhysicalSimon, MockPhysicalTimer, mock_can_bus
from bombgame.utils import FatalError

LOGGER = getLogger("BombGameTest")


def main():
    init_logging()
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    LOGGER.info("In asyncio shell, Ctrl-D, exit() or others cause unclean exit")
    LOGGER.info("You have the following variables:")
    LOGGER.info("  timer, simon - virtual modules already created for you")
    LOGGER.info("  bus - the BombBus viewed from the virtual module side, gets controller's messages")
    LOGGER.info("  gpio - the MockGpio for the virtual bomb")
    LOGGER.info("  loop - the running event loop")
    quit_evt = handle_sigint()
    init_game()
    gpio = MockGpio()
    mock_side_can = mock_can_bus()
    mock_side_bus = BombBus(mock_side_can)
    mock_side_bus.add_listener(FatalError, handle_fatal_error)
    mock_side_bus.start()
    timer = MockPhysicalTimer(mock_side_bus, gpio, 0)
    simon = MockPhysicalSimon(mock_side_bus, gpio, 1)
    controller_side_can = mock_can_bus()

    async def run_and_cleanup():
        await run_game(controller_side_can, gpio, quit_evt)
        mock_side_bus.stop()
        LOGGER.info("Exiting")
        get_running_loop().stop()
    create_task(run_and_cleanup())

    return {
        "timer": timer,
        "simon": simon,
        "bus": mock_side_bus,
        "gpio": gpio,
        "loop": get_running_loop()
    }
