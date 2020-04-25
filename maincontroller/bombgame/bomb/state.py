from enum import Enum


class BombState(Enum):
    UNINITIALIZED = 0
    RESETTING = 1
    INITIALIZING = 2
    INITIALIZED = 3
    GAME_STARTING = 4
    GAME_STARTED = 5
    GAME_PAUSED = 6
    DEFUSED = 7
    EXPLODED = 8
    INITIALIZATION_FAILED = -1
    DEINITIALIZED = -2