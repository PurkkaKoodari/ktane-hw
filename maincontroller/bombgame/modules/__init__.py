MODULE_NAMES = [
    "SimonSays"
]

def load_modules():
    for module_name in MODULE_NAMES:
        __import__("bombgame.modules." + module_name.lower())
