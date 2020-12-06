"""Provides a way to run the game and interact with it from the asyncio shell. Also provides a virtual bomb to run
the game with.

Usage:

1. Start the asyncio shell by typing ``python -m asyncio`` (requires Python 3.8+).
2. Import the shell: ``from bombgame.test.shell import start_real`` (use ``start_mock`` for a virtual bomb)
3. Run the game and get variables to interact with it: ``locals().update(await start_real())``
4. Interact with the game from the shell
5. Kill the game task and exit the shell by pressing Ctrl-C
"""

from __future__ import annotations

from asyncio import create_task, get_running_loop
from logging import getLogger

from bombgame.bus.bus import BombBus
from bombgame.controller import handle_fatal_error, BombGameController
from bombgame.logging import init_logging
from bombgame.test.mock import MockGpio, MockPhysicalSimon, MockPhysicalTimer, mock_can_bus
from bombgame.utils import FatalError, log_errors, handle_sigint

LOGGER = getLogger("BombGameTest")


async def start_mock():
    init_logging(True)
    LOGGER.info("Starting. Stop the game cleanly with SIGINT/Ctrl-C")
    LOGGER.info("In asyncio shell, Ctrl-D, exit() and others cause unclean exit")
    LOGGER.info("You have the following variables:")
    LOGGER.info("  timer, simon - virtual modules already created for you")
    LOGGER.info("  bus - the BombBus viewed from the virtual module side, receives the controller's messages")
    LOGGER.info("  can_bus - the virtual CAN bus underlying the BombBus")
    LOGGER.info("  gpio - the MockGpio used by the virtual bomb")
    LOGGER.info("  game - the BombGameController")
    LOGGER.info("  loop - the running event loop")
    quit_evt = handle_sigint()
    # create mock GPIO
    gpio = MockGpio()
    # create mock physical bomb
    mock_side_can = mock_can_bus()
    mock_side_bus = BombBus(mock_side_can)
    mock_side_bus.add_listener(FatalError, handle_fatal_error)
    mock_side_bus.start()
    timer = MockPhysicalTimer(mock_side_bus, gpio, 0)
    simon = MockPhysicalSimon(mock_side_bus, gpio, 1)
    # initialize game with these
    controller_side_can = mock_can_bus()
    game = BombGameController(controller_side_can, gpio)
    await game.start()

    async def run_and_cleanup():
        await quit_evt.wait()
        await game.stop()
        mock_side_bus.stop()
        LOGGER.info("The game has exited. You can now exit with Ctrl-D/exit()")
    create_task(log_errors(run_and_cleanup()))

    return {
        "timer": timer,
        "simon": simon,
        "bus": mock_side_bus,
        "can_bus": mock_side_can,
        "gpio": gpio,
        "game": game,
        "loop": get_running_loop()
    }


async def start_real():
    init_logging(True)
    LOGGER.info("Starting. Stop the game cleanly with SIGINT/Ctrl-C")
    LOGGER.info("In asyncio shell, Ctrl-D, exit() and others cause unclean exit")
    LOGGER.info("You have the following variables:")
    LOGGER.info("  game - the BombGameController")
    LOGGER.info("  loop - the running event loop")
    quit_evt = handle_sigint()
    game = BombGameController()
    await game.start()

    async def run_and_cleanup():
        await quit_evt.wait()
        await game.stop()
        LOGGER.info("The game has exited. You can now exit with Ctrl-D/exit()")
    create_task(log_errors(run_and_cleanup()))

    return {
        "game": game,
        "loop": get_running_loop(),
    }
