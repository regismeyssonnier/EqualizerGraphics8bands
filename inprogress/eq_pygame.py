import pygame
import sys

import numpy as np
import matplotlib.pyplot as plt
import sounddevice as sd
from threading import Lock
import time
import os
import subprocess
import tempfile
from scipy.io import wavfile


from ui import *
from eq import *

COULEUR_FOND = (30, 30, 30)



# Initialisation de Pygame
pygame.init()

# Constantes
LARGEUR, HAUTEUR = 800, 600

# Création de la fenêtre
fenetre = pygame.display.set_mode((LARGEUR, HAUTEUR))
pygame.display.set_caption("Equalizer 8 bands")
horloge = pygame.time.Clock()

eq = EqualizerAudio('next.mp3')
eq.start_playback()

equalizer8Bands = Equalizer8Bands(fenetre, 100, 100, eq)



# Boucle principale
while True:
    for evenement in pygame.event.get():
        if evenement.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        
        equalizer8Bands.Event(evenement)

    # Remplir l'arrière-plan
    fenetre.fill(COULEUR_FOND)

    equalizer8Bands.draw()

    # Mettre à jour l'affichage
    pygame.display.flip()
    horloge.tick(60)