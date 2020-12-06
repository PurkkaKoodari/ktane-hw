from bombgame.casings import VanillaCasing

# the physical bomb casing mounted on the RasPi
BOMB_CASING = VanillaCasing()

# the configuration for can.Bus
CAN_CONFIG = {"interface": "socketcan", "channel": "can0"}

# the URL of the room server, or None if none is in use
# example: ROOM_SERVER = "ws://192.168.0.123:8082/"
ROOM_SERVER = None
# the authentication key for the room server
ROOM_SERVER_AUTH_KEY = "password"  # TODO: change for production use
# the port to host the room server on (only relevant when running room server on this machine)
ROOM_SERVER_PORT = 8082
# the timeout for authentication, in seconds (only relevant when running room server on this machine)
ROOM_SERVER_AUTH_TIMEOUT = 2

# whether or not audio playback commands should be sent to the room server
ROOM_AUDIO_ENABLED = True
# whether or not DMX commands should be sent to the room server
ROOM_DMX_ENABLED = True
# whether or not to host the Web UI on the room server
ROOM_WEB_UI_ENABLED = False

# the API URL of the QLC+ light controller, or None if none is in use
# example: DMX_SERVER = "ws://127.0.0.1:9999/qlcplusWS"
DMX_SERVER = None

# how many simultaneous sound effects to support
AUDIO_CHANNELS = 16

# how often to manually check GPIO pins for changes
GPIO_POLL_INTERVAL = 1.0
# the address of the I2C bus where the expanders are connected
GPIO_SMBUS_ADDR = 1
# whether or not to enable GPIO interrupts
GPIO_INTERRUPT_ENABLED = True
# the RasPi pin where the interrupts are connected
GPIO_INTERRUPT_PIN = 22  # TODO: check actual pin number

# if CAN_ERROR_MAX_COUNT bus errors are encountered in CAN_ERROR_MAX_INTERVAL seconds, a fatal error is raised
CAN_ERROR_MAX_INTERVAL = 15
CAN_ERROR_MAX_COUNT = 10

# websocket runs at 0.0.0.0 on this port
WEB_WS_PORT = 8081
# the password required from the UI
WEB_PASSWORD = None
# the timeout for sending the password, in seconds
WEB_LOGIN_TIMEOUT = 2

# the time waited between sending the reset message and checking which modules are ready
MODULE_RESET_PERIOD = 0.6
# the time waited for a module to respond to the MODULE_ENABLE line
MODULE_ANNOUNCE_TIMEOUT = 1.0
# the time waited after a module's last message before pinging it
# set to slightly over 1s to avoid unnecessarily pinging the timer
MODULE_PING_INTERVAL = 0.99  # TODO: 1.2
# the time waited after sending a ping before causing a ping timeout error
MODULE_PING_TIMEOUT = 1.0

# the time spent in the pre-game wait
GAME_START_DELAY = 5

# the default number of strikes before the bomb explodes
DEFAULT_MAX_STRIKES = 3
