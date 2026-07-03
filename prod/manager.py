import os
import logging

class Manager:
    def __init__(self, fichier_ini="config.ini", logger=None):
        """
        Manager avec logging
        
        Args:
            fichier_ini (str): Chemin vers le fichier .ini
            logger: Objet logger personnalisé
        """
        self.fichier_ini = fichier_ini
        self.logger = logger or self._creer_logger()
        self.variables = {}  # Stockage centralisé
        self.charger_config()
    
    def _creer_logger(self):
        """Crée un logger par défaut"""
        logger = logging.getLogger('Manager')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            logger.addHandler(handler)
        return logger
    
    def charger_config(self):
        """Charge la configuration"""
        if not os.path.exists(self.fichier_ini):
            self.logger.warning(f"Fichier {self.fichier_ini} non trouvé")
            return
        
        try:
            with open(self.fichier_ini, 'r', encoding='utf-8') as f:
                for num, ligne in enumerate(f, 1):
                    ligne = ligne.strip()
                    
                    if not ligne or ligne.startswith('#'):
                        continue
                    
                    if '=' not in ligne:
                        self.logger.warning(f"Ligne {num} ignorée (pas de '='): {ligne}")
                        continue
                    
                    try:
                        cle, valeur = ligne.split('=', 1)
                        cle = cle.strip()
                        valeur = valeur.strip()
                        
                        valeur_convertie = self._convertir(valeur)
                        
                        # Stocker dans les deux formats
                        setattr(self, cle, valeur_convertie)
                        self.variables[cle] = valeur_convertie
                        
                        self.logger.debug(f"✅ {cle} = {valeur_convertie}")
                    
                    except Exception as e:
                        self.logger.error(f"Ligne {num} invalide: {ligne} - {e}")
        
        except Exception as e:
            self.logger.error(f"Erreur de lecture: {e}")
    
    def _convertir(self, valeur):
        """Convertit la valeur"""
        # Booléen
        if valeur.lower() in ('true', 'yes', 'on'):
            return True
        if valeur.lower() in ('false', 'no', 'off'):
            return False
        
        # Nombre
        try:
            if '.' in valeur:
                return float(valeur)
            return int(valeur)
        except:
            pass
        
        # Liste
        if ',' in valeur:
            return [item.strip() for item in valeur.split(',')]
        
        return valeur
    
    def get(self, cle, defaut=None):
        """Récupère une variable avec valeur par défaut"""
        return self.variables.get(cle, defaut)
    
    def set(self, cle, valeur):
        """Modifie une variable"""
        self.variables[cle] = valeur
        setattr(self, cle, valeur)
    
    def reload(self):
        """Recharge la configuration"""
        self.variables.clear()
        self.charger_config()
    
    def afficher(self):
        """Affiche toutes les variables"""
        print("\n📋 Configuration actuelle:")
        for cle, valeur in sorted(self.variables.items()):
            print(f"  {cle} = {valeur}")

