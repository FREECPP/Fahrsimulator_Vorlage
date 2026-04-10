import os
import re
import configparser


def init_base_dir():
    """Erstellt das Basis-Verzeichnis, falls nicht vorhanden"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini nicht gefunden: {config_path}")
    config.read(config_path)
    base_dir = config.get('General', 'BASE_DIR')
        
    os.makedirs(base_dir, exist_ok=True)
    
    return base_dir

def get_directories(base_dir):
    """Gibt alle Verzeichnisse im BASE_DIR zurück"""
    if not os.path.exists(base_dir):
        return []
    return [d for d in os.listdir(base_dir) 
            if os.path.isdir(os.path.join(base_dir, d))]

def validate_name(name):
    """Validiert den Namen (4+ Zeichen, nur A-Z, a-z, 0-9, _, -)"""
    pattern = r"^[A-Za-z0-9_-]{4,}$"
    return bool(re.match(pattern, name))

def directory_exists(base_dir, name):
    """Prüft ob ein Verzeichnis existiert"""
    dir_path = os.path.join(base_dir, name)
    return os.path.exists(dir_path)

def create_directory(base_dir, name):
    """Erstellt ein neues Verzeichnis"""
    dir_path = os.path.join(base_dir, name)
    os.makedirs(dir_path)
    return dir_path

def get_directory_path(base_dir, name):
    """Gibt den vollständigen Pfad eines Verzeichnisses zurück"""
    return os.path.join(base_dir, name)

