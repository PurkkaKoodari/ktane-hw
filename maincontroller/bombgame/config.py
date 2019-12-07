from bombgame.casings import VanillaCasing

BOMB_CASING = VanillaCasing()

CAN_CONFIG = {"interface": "socketcan", "channel": "can0"}

ROOM_SERVER = None
ROOM_AUDIO_ENABLED = True

AUDIO_CHANNELS = 16

GPIO_POLL_INTERVAL = 1.0
GPIO_SMBUS_ADDR = 1
GPIO_INTERRUPT_ENABLED = True
GPIO_INTERRUPT_PIN = 22  # TODO: check actual pin number

# if we encounter 10 errors in 15 seconds, raise a fatal error
CAN_ERROR_MAX_INTERVAL = 15
CAN_ERROR_MAX_COUNT = 10
