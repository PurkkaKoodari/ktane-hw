MODULE_NAMES = [
    "Timer",
    "SimonSays",
    "Keypad",
    "Wires",
    "Password",
    "Button",
    "ComplicatedWires",
]


def load_modules():
    for module_name in MODULE_NAMES:
        __import__("bombgame.modules." + module_name.lower())
