import pygame

SOUND_REGISTRY = {}

LOADED_SOUNDS = {}

def register_sounds(module_class, sounds):
    SOUND_REGISTRY[module_class] = sounds

def load_sounds(module_classes):
    for module_class in module_classes:
        for sound in SOUND_REGISTRY[module_class]:
            if sound not in LOADED_SOUNDS:
                LOADED_SOUNDS[sound] = pygame.mixer.Sound(sound) # TODO: locate sound folders

def initialize_local_playback():
    pygame.mixer.init()

def get_channel_configuration():
    raise NotImplementedError

# TODO: remote playback for roomscale
# TODO: music system
