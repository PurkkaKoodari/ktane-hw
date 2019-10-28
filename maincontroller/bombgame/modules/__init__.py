from .base import Module, NeedyModule, MODULE_NAMES, MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

def load_modules():
    for module_name in MODULE_NAMES:
        __import__("bombgame.modules." + module_name.lower())
