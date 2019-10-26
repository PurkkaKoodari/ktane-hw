from .base import Module, NeedyModule, MODULES, MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

def load_modules():
    for module_name in MODULES:
        __import__("bombgame.modules." + module_name.lower())
