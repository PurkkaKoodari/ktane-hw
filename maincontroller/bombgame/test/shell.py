from asyncio import wrap_future, run, get_running_loop
from code import interact

from .mock import MockGpio, MockPhysicalSimon, MockPhysicalTimer, mock_can_bus
from ..bus.bus import BombBus
from ..controller import init_game, run_game, handle_fatal_error
from ..utils import AuxiliaryThreadExecutor, FatalError


async def run_repl(local):
    repl = AuxiliaryThreadExecutor(name="REPL")
    repl.start()
    await wrap_future(repl.submit(lambda: interact(local=local)))
    repl.shutdown()


async def run_test_shell():
    init_game()
    gpio = MockGpio()
    mock_side_can = mock_can_bus()
    mock_side_bus = BombBus(mock_side_can)
    mock_side_bus.add_listener(FatalError, handle_fatal_error)
    mock_side_bus.start()
    timer = MockPhysicalTimer(mock_side_bus, gpio, 0)
    simon = MockPhysicalSimon(mock_side_bus, gpio, 1)
    local = {
        "timer": timer,
        "simon": simon,
        "bus": mock_side_bus,
        "gpio": gpio,
        "loop": get_running_loop()
    }
    controller_side_can = mock_can_bus()
    # TODO make this work with Python 3.8's asyncio shell
    await run_game(controller_side_can, gpio, run_repl(local))
    mock_side_bus.stop()


if __name__ == '__main__':
    run(run_test_shell())
