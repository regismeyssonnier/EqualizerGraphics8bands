import pygame
import sys
import numpy as np
import random
import os

from eq import *

#Color
COLOR_RED = (255, 0, 0)
COLOR_BLV = (0, 100, 150)
COLOR_OUTPUTBASE = (100, 100, 100)
COLOR_BUTTON = (150, 120, 0)

class SliderV:

    def __init__(self, window, parentX, parentY, name = "sliderV", valMin=-30, valMax=30):
        self.name = name
        self.margin = 10
        self.x = parentX + self.margin
        self.y = parentY + self.margin
        self.startX = self.x
        self.startY = self.y
        self.w = 10
        self.h = 200
        self.valMin = valMin
        self.valMax = valMax

        self.butt_w = 20 + self.margin
        self.butt_h = 20
        self.x_butt = self.x - self.butt_w // 2 + self.w // 2
        self.y_butt = self.startY + self.h // 2

        self.butt_pushed = False
        self.butt_offset_x = 0
        self.butt_offset_y = self.startY + self.h // 2
        self.window = window
        self.value = (self.valMax + self.valMin) // 2 - self.valMin
                
    
    def is_on_butt(self, mouse_x, mouse_y):
        """Vérifie si les coordonnées de la souris sont sur le carré"""
        return (self.x_butt <= mouse_x <= self.x_butt + self.butt_w and
                self.y_butt <= mouse_y <= self.y_butt + self.butt_h)

    def draw(self):

        pygame.draw.rect(self.window, COLOR_BLV, (self.x, self.y, self.w, self.h))

        pygame.draw.rect(self.window, COLOR_RED, (self.x_butt, self.y_butt, self.butt_w, self.butt_h))

        
    def set_value(self, v):
        """
        Définit la valeur du slider et met à jour la position du bouton
        
        Args:
            v: Nouvelle valeur (doit être entre valMin et valMax)
        """
        # Clipper la valeur entre les limites
        self.value = np.clip(v, self.valMin, self.valMax)
        
        # Calculer la position du bouton (inversé car y augmente vers le bas)
        # Quand value = valMin -> bouton en bas (startY + h)
        # Quand value = valMax -> bouton en haut (startY)
        ratio = (self.value - self.valMin) / (self.valMax - self.valMin)
        self.y_butt = self.startY + self.h - (ratio * self.h)
        
        # S'assurer que le bouton reste dans les limites
        self.y_butt = np.clip(self.y_butt, self.startY, self.startY + self.h)

    def Event(self, event, object_event):

        # Détection du clic enfoncé (mousebuttondown)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Bouton gauche
                souris_x, souris_y = event.pos
                if self.is_on_butt(souris_x, souris_y):
                    self.butt_pushed = True
                    self.butt_offset_x = souris_x - self.x_butt
                    self.butt_offset_y = souris_y - self.y_butt
                else:
                    self.butt_pushed = False
        
        # Détection du relâchement (mousebuttonup)
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Bouton gauche
                if self.butt_pushed:  # Seulement si on avait cliqué dessus
                    # Réinitialisation des états
                    self.butt_pushed = False

        if event.type == pygame.MOUSEMOTION:
            if self.butt_pushed:
                souris_x, souris_y = event.pos
                self.y_butt = np.clip(souris_y - self.butt_offset_y, self.startY, self.startY + self.h)
                self.value = np.clip((1.0 - ((self.y_butt - self.startY) / self.h)) * (self.valMax - self.valMin) + self.valMin, self.valMin, self.valMax)

                if object_event is not None:
                    object_event.on_move()


class OutputEqualizer:

    def __init__(self, window, baseX, baseY, name = "OutputEq", valMin=-60, valMax=60):

        self.name = name
        self.margin = 10
        self.x = baseX + self.margin
        self.y = baseY + self.margin
        self.startX = self.x
        self.startY = self.y
        self.w = 20
        self.h = 200
        self.valMin = valMin
        self.valMax = valMax

        self.window = window
        self.value = 0

    def SetValueOutput(self, v):
        self.value = np.clip(v, self.valMin, self.valMax)
                        

    def draw(self):

        pygame.draw.rect(self.window, COLOR_OUTPUTBASE, (self.x, self.y, self.w, self.h))

        color = (0,0,0)
        amp = self.value
        if amp > 0:
            color = (255, 0, 0)        # #ff0000 - Rouge pur
        elif amp > -6:
            color = (255, 68, 0)       # #ff4400 - Rouge orangé
        elif amp > -12:
            color = (255, 136, 0)      # #ff8800 - Orange
        elif amp > -18:
            color = (255, 204, 0)      # #ffcc00 - Jaune orangé
        elif amp > -24:
            color = (102, 255, 102)    # #66ff66 - Vert clair
        elif amp > -30:
            color = (0, 221, 255)      # #00ddff - Cyan
        elif amp > -40:
            color = (0, 153, 255)      # #0099ff - Bleu ciel
        elif amp > -50:
            color = (0, 102, 204)      # #0066cc - Bleu moyen
        else:
            color = (0, 51, 102)       # #003366 - Bleu foncé

        if self.value <= 0:
            pygame.draw.rect(self.window, color, (self.x, self.y+self.h//2, self.w, abs(self.value) / (self.valMax - self.valMin) * self.h))
        else:
            heightvalue = abs(self.value) / (self.valMax - self.valMin) * self.h
            pygame.draw.rect(self.window, color, (self.x, self.y+self.h//2-heightvalue, self.w, heightvalue))


class Button:

    def __init__(self, window, parentX, parentY, width=150, height=50, name = "sliderV", value="button"):
        self.window = window
        self.name = name
        self.margin = 10
        self.x = parentX + self.margin
        self.y = parentY + self.margin
        self.startX = self.x
        self.startY = self.y
        self.w = width
        self.h = height
        self.value = value


    def is_on_butt(self, mouse_x, mouse_y):
        """Vérifie si les coordonnées de la souris sont sur le carré"""
        return (self.x <= mouse_x <= self.x + self.w and
                self.y <= mouse_y <= self.y + self.h)

    def draw(self):

        pygame.draw.rect(self.window, COLOR_BUTTON, (self.x, self.y, self.w, self.h))
        self.display_text(self.value, self.x + self.w//2 - len(self.value)*5, self.y + self.h//2 - 7)

    def display_text(self, texte, x, y, taille=20, couleur=(255,255,255), police=None):
        """Affiche du texte sur une surface"""
        font = pygame.font.Font(police, taille) if police else pygame.font.Font(None, taille)
        texte_surface = font.render(texte, True, couleur)
        self.window.blit(texte_surface, (x, y))
        return texte_surface.get_rect(topleft=(x, y))

    def Event(self, event, object_event):
        
        # Détection du relâchement (mousebuttonup)
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Bouton gauche
                souris_x, souris_y = event.pos
                if self.is_on_butt(souris_x, souris_y):
                    if object_event is not None:
                        object_event.on_click()

class Equalizer8Bands:

    def __init__(self, window, baseX, baseY, equalizer, manager=None):

        self.window = window
        self.equalizer = equalizer
        self.baseX = baseX
        self.baseY = baseY

        self.width_button_player = 75
        self.margin_button_player = 10
        self.back = Button(window, baseX-90, baseY-75, width=self.width_button_player, height=20, name="ButtonBack", value="<<")
        self.play = Button(window, baseX-90+self.width_button_player+self.margin_button_player, baseY-75, width=self.width_button_player, height=20, name="ButtonPlay", value="Play")
        self.pause = Button(window, baseX-90+self.width_button_player*2+self.margin_button_player*2, baseY-75, width=self.width_button_player, height=20, name="ButtonPause", value="Pause")
        self.stop = Button(window, baseX-90+self.width_button_player*3+self.margin_button_player*3, baseY-75, width=self.width_button_player, height=20, name="ButtonStop", value="Stop")
        self.next = Button(window, baseX-90+self.width_button_player*4+self.margin_button_player*4, baseY-75, width=self.width_button_player, height=20, name="ButtonNext", value=">>")
        self.reset = Button(window, baseX-90+self.width_button_player*5+self.margin_button_player*5, baseY-75, width=self.width_button_player, height=20, name="ButtonReset", value="Reset")

        
        self.sliderV = []
        self.sliderV.append(SliderV(window, baseX, baseY, "slider62"))
        self.sliderV.append(SliderV(window, baseX+50, baseY, "slider125"))
        self.sliderV.append(SliderV(window, baseX+100, baseY, "slider250"))
        self.sliderV.append(SliderV(window, baseX+150, baseY, "slider500"))
        self.sliderV.append(SliderV(window, baseX+200, baseY, "slider1k"))
        self.sliderV.append(SliderV(window, baseX+250, baseY, "slider2k"))
        self.sliderV.append(SliderV(window, baseX+300, baseY, "slider4k"))
        self.sliderV.append(SliderV(window, baseX+350, baseY, "slider8k"))

        self.path_music = '.'
        self.index_player = 0
        if manager is not None:
            self.path_music = manager.folder_music
            self.index_player = manager.index_player

        

        audio_files = []
        for f in os.listdir(self.path_music):
            if f.endswith(('.wav', '.WAV', '.mp3', '.MP3', '.flac', '.FLAC', '.m4a', '.M4A')):
                audio_files.append(f)
        self.audio_playname = audio_files[self.index_player]


        class EventButtonBack:

            def __init__(self, button, equalizer, parent):
                self.button = button
                self.equalizer = equalizer
                self.parent = parent

            def on_click(self):

                if self.equalizer.running:
                    self.equalizer.stop_playback()
   
                audio_files = []
                for f in os.listdir(self.parent.path_music):
                    if f.endswith(('.wav', '.WAV', '.mp3', '.MP3', '.flac', '.FLAC', '.m4a', '.M4A')):
                        audio_files.append(f)

                self.parent.index_player = (self.parent.index_player - 1 + len(audio_files)) % len(audio_files)
                self.parent.audio_playname = audio_files[self.parent.index_player]
                #self.equalizer.reset(audio_files[self.parent.index_player])
                #self.equalizer.start_playback()
         
        self.buttonBackEvent = EventButtonBack(self.back, equalizer, self)

        class EventButtonNext:

            def __init__(self, button, equalizer, parent):
                self.button = button
                self.equalizer = equalizer
                self.parent = parent

            def on_click(self):

                if self.equalizer.running:
                    self.equalizer.stop_playback()

                audio_files = []
                for f in os.listdir(self.parent.path_music):
                    if f.endswith(('.wav', '.WAV', '.mp3', '.MP3', '.flac', '.FLAC', '.m4a', '.M4A')):
                        audio_files.append(f)

                self.parent.index_player = (self.parent.index_player + 1) % len(audio_files)
                self.parent.audio_playname = audio_files[self.parent.index_player]
                #self.equalizer.reset(audio_files[self.parent.index_player])
                #self.equalizer.start_playback()
         
        self.buttonNextEvent = EventButtonNext(self.next, equalizer, self)

        class EventButtonPlay:

            def __init__(self, button, equalizer, parent):
                self.button = button
                self.equalizer = equalizer
                self.parent = parent
                self.already_apply = False

            def on_click(self):
   
                if not self.equalizer.running:
                    audio_files = []
                    for f in os.listdir(self.parent.path_music):
                        if f.endswith(('.wav', '.WAV', '.mp3', '.MP3', '.flac', '.FLAC', '.m4a', '.M4A')):
                            audio_files.append(f)

                    self.equalizer.reset(audio_files[self.parent.index_player])
                    
                    for idx, slv in enumerate(self.parent.sliderV):
                        self.equalizer.set_gain(idx, slv.value)

                    self.equalizer.volume = self.parent.sliderSound.value / 100.0
                    print(self.equalizer.volume)
                    self.already_apply = True

                    self.equalizer.start_playback()
                else:
                    self.equalizer.paused = False
                    self.already_apply =False

        self.buttonPlayEvent = EventButtonPlay(self.play, equalizer, self)

        class EventButtonPause:

            def __init__(self, button, equalizer):
                self.button = button
                self.equalizer = equalizer

            def on_click(self):
                if self.equalizer.running:
                    self.equalizer.paused = True

        self.buttonPauseEvent = EventButtonPause(self.pause, equalizer)

        class EventButtonStop:

            def __init__(self, button, equalizer):
                self.button = button
                self.equalizer = equalizer

            def on_click(self):
                if self.equalizer.running:
                    self.equalizer.stop_playback()

        self.buttonStopEvent = EventButtonStop(self.stop, equalizer)

        class EventButtonReset:

            def __init__(self, button, equalizer, parent):
                self.button = button
                self.equalizer = equalizer
                self.parent = parent

            def on_click(self):
                for idx, slv in enumerate(self.parent.sliderV):
                    slv.set_value(0)

                self.parent.sliderSound.set_value(50)

                for idx, slv in enumerate(self.parent.sliderV):
                    self.equalizer.set_gain(idx, slv.value)

                self.equalizer.volume = self.parent.sliderSound.value / 100.0
                print(self.equalizer.volume)

        self.buttonResetEvent = EventButtonReset(self.reset, equalizer, self)


        self.sliderSound = SliderV(window, baseX-90, baseY, "sliderSound", 0, 100)

        class Event_SliderSound:
            def __init__(self, sliderV, equalizer):
                self.sliderV = sliderV
                self.equalizer = equalizer
              

            def on_move(self):
                print(self.sliderV.name, self.sliderV.value)
                self.equalizer.volume = self.sliderV.value / 100.0
                #print(self.equalizer.volume)

        self.sliderSoundEvent = Event_SliderSound(self.sliderSound, self.equalizer)
                        
        
                     

        self.baseYoutputEq = 250 

        self.outputEqV = []
        self.outputEqV.append(OutputEqualizer(window, baseX, baseY+self.baseYoutputEq, "outputEqV62"))
        self.outputEqV.append(OutputEqualizer(window, baseX+50, baseY+self.baseYoutputEq, "outputEqV125"))
        self.outputEqV.append(OutputEqualizer(window, baseX+100, baseY+self.baseYoutputEq, "outputEqV250"))
        self.outputEqV.append(OutputEqualizer(window, baseX+150, baseY+self.baseYoutputEq, "outputEqV500"))
        self.outputEqV.append(OutputEqualizer(window, baseX+200, baseY+self.baseYoutputEq, "outputEqV1k"))
        self.outputEqV.append(OutputEqualizer(window, baseX+250, baseY+self.baseYoutputEq, "outputEqV2k"))
        self.outputEqV.append(OutputEqualizer(window, baseX+300, baseY+self.baseYoutputEq, "outputEqV4k"))
        self.outputEqV.append(OutputEqualizer(window, baseX+350, baseY+self.baseYoutputEq, "outputEqV8k"))

        #for oe in self.outputEqV:
        #    oe.SetValueOutput(random.randint(-60,60))


        class Event_SliderV:
            def __init__(self, sliderV, outputEq, equalizer, idx=0):
                self.sliderV = sliderV
                self.outputEq = outputEq
                self.equalizer = equalizer
                self.idx = idx

            def on_move(self):
                print(self.sliderV.name, self.sliderV.value)
                self.equalizer.set_gain(self.idx, self.sliderV.value)
                

        self.sliderEvent = []
        self.sliderEvent.append(Event_SliderV(self.sliderV[0], self.outputEqV[0], equalizer, 0))
        self.sliderEvent.append(Event_SliderV(self.sliderV[1], self.outputEqV[1], equalizer, 1))
        self.sliderEvent.append(Event_SliderV(self.sliderV[2], self.outputEqV[2], equalizer, 2))
        self.sliderEvent.append(Event_SliderV(self.sliderV[3], self.outputEqV[3], equalizer, 3))
        self.sliderEvent.append(Event_SliderV(self.sliderV[4], self.outputEqV[4], equalizer, 4))
        self.sliderEvent.append(Event_SliderV(self.sliderV[5], self.outputEqV[5], equalizer, 5))
        self.sliderEvent.append(Event_SliderV(self.sliderV[6], self.outputEqV[6], equalizer, 6))
        self.sliderEvent.append(Event_SliderV(self.sliderV[7], self.outputEqV[7], equalizer, 7))

    def display_text(self, texte, x, y, taille=20, couleur=(255,255,255), police=None):
        """Affiche du texte sur une surface"""
        font = pygame.font.Font(police, taille) if police else pygame.font.Font(None, taille)
        texte_surface = font.render(texte, True, couleur)
        self.window.blit(texte_surface, (x, y))
        return texte_surface.get_rect(topleft=(x, y))

    def draw(self):

        self.back.draw()
        self.play.draw()
        self.pause.draw()
        self.stop.draw()
        self.next.draw()
        self.reset.draw()

        for sl in self.sliderV:
            sl.draw()

        amp = self.equalizer.get_amplitudes()
        for idx, oe in enumerate(self.outputEqV):
            oe.SetValueOutput(amp[idx])
            oe.draw()

        self.sliderSound.draw()
            
        self.display_text('Play now ' + self.audio_playname, self.baseX-90, self.baseY-90)

        self.display_text(str(int(self.sliderSound.value)), self.baseX-90, self.baseY-20)
        self.display_text('Sound', self.baseX-90, self.baseY+self.sliderV[0].h+20)

        self.display_text('+30db', self.baseX+390, self.baseY+10, 14)
        self.display_text('0db', self.baseX+390, self.baseY+10+self.sliderV[0].h//2, 14)
        self.display_text('-30db', self.baseX+390, self.baseY+10+self.sliderV[0].h, 14)

        self.display_text('+60db', self.baseX+390, self.baseY+self.baseYoutputEq+10, 14)
        self.display_text('0db', self.baseX+390, self.baseY+self.baseYoutputEq+10+self.sliderV[0].h//2, 14)
        self.display_text('-60db', self.baseX+390, self.baseY+self.baseYoutputEq+10+self.sliderV[0].h, 14)

        self.display_text('62hz', self.baseX, self.baseY+self.sliderV[0].h+20)
        self.display_text('125hz', self.baseX+50, self.baseY+self.sliderV[0].h+20)
        self.display_text('250hz', self.baseX+100, self.baseY+self.sliderV[0].h+20)
        self.display_text('500hz', self.baseX+150, self.baseY+self.sliderV[0].h+20)
        self.display_text('1Khz', self.baseX+200, self.baseY+self.sliderV[0].h+20)
        self.display_text('2Khz', self.baseX+250, self.baseY+self.sliderV[0].h+20)
        self.display_text('4Khz', self.baseX+300, self.baseY+self.sliderV[0].h+20)
        self.display_text('8Khz', self.baseX+350, self.baseY+self.sliderV[0].h+20)

    def Event(self, event):

        for ix, sl in enumerate(self.sliderV):
            sl.Event(event, self.sliderEvent[ix])

        self.sliderSound.Event(event, self.sliderSoundEvent)

        self.back.Event(event, self.buttonBackEvent)
        self.play.Event(event, self.buttonPlayEvent)
        self.pause.Event(event, self.buttonPauseEvent)
        self.stop.Event(event, self.buttonStopEvent)
        self.next.Event(event, self.buttonNextEvent)
        self.reset.Event(event, self.buttonResetEvent)