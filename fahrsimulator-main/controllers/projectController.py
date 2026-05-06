import os  # Betriebssystem-Funktionen (z. B. Pfade, Ordner erstellen)

from flask_cors import cross_origin  # Ermöglicht Cross-Origin Requests für einzelne Routen
from extensions import db  # Datenbank-Instanz (SQLAlchemy)
from flask import Blueprint, render_template, request, jsonify  # Flask-Komponenten

# Eigene Utility-Funktionen für Verzeichnisverwaltung
from utils.verzeichnis_utils import (
    init_base_dir,        # Initialisiert Basisverzeichnis
    get_directories,      # Gibt Unterordner zurück
    validate_name,        # Validiert Namen (z. B. keine Sonderzeichen)
    directory_exists,     # Prüft, ob Verzeichnis existiert
    create_directory      # Erstellt ein Verzeichnis
)

from dbModels.projectAndParticipantsDB import Project, Participant  # Datenbankmodelle
from datetime import datetime  # Für Zeitstempel
from flask_cors import CORS  # Aktiviert CORS global für Blueprint


# Blueprint definieren (Modul für Routen)
verzeichnis_bp = Blueprint(
    'verzeichnis',
    __name__,
    url_prefix='/',  # Basis-URL
    template_folder='../templates'  # Ordner für HTML-Templates
)

CORS(verzeichnis_bp)  # Aktiviert CORS für alle Routen dieses Blueprints

base_dir = init_base_dir()  # Basisverzeichnis initialisieren
project_path = None  # Globaler Speicher für aktuell gewählten Projektpfad


# Startseite
@verzeichnis_bp.route('/')
def index():
    directories = get_directories(base_dir)  # Alle Verzeichnisse laden
    return render_template('index.html', directories=directories)  # an Template übergeben


# API: Alle Verzeichnisse abrufen
@verzeichnis_bp.route('/api/verzeichnisse', methods=['GET'])
def get_dirs():
    return jsonify(get_directories(base_dir))  # JSON-Antwort


# API: Alle Projekte abrufen
@verzeichnis_bp.route('/api/projects', methods=['GET'])
def get_projects():
    sync_project_availability()  # Prüft, ob Projektordner noch existieren
    projects = Project.query.all()  # Alle Projekte aus DB
    return jsonify([p.to_dict() for p in projects])  # In JSON umwandeln


# Neues Verzeichnis (Projekt) erstellen
@verzeichnis_bp.route('/vz_anlegen', methods=['POST'])
def create():
    verzeichnis = request.form.get('projektverzeichnis', '').strip()  # Name holen
    creator = request.form.get('creator', 'Unbekannt')  # Ersteller

    # Name validieren
    if not validate_name(verzeichnis):
        return jsonify({'success': False}), 400

    # Prüfen, ob Projekt schon existiert
    existing = Project.query.filter_by(name=verzeichnis).first()
    if existing:
        return jsonify({'success': False, 'message': 'existiert schon'}), 400

    try:
        full_path = os.path.join(base_dir, verzeichnis)  # Vollständiger Pfad
        create_directory(base_dir, verzeichnis)  # Ordner erstellen

        # Neues Projekt-Objekt erstellen
        new_project = Project(
            name=verzeichnis,
            path=full_path,
            creator=creator
        )

        db.session.add(new_project)  # In DB speichern
        db.session.commit()

        return jsonify({
            'success': True,
            'project': new_project.to_dict()
        })

    except Exception as e:
        db.session.rollback()  # Fehler -> Änderungen zurückrollen
        return jsonify({'error': str(e)}), 500


# Projekt auswählen
@verzeichnis_bp.route('/vz_select', methods=['POST'])
def select():
    global project_path  # Globale Variable verwenden

    projekt_verzeichnis = request.form.get('existierendesVerzeichnis', '').strip()
    projekt_name = request.form.get('projektname', '').strip()

    base_project_path = os.path.join(base_dir, projekt_verzeichnis)
    project_path = os.path.join(base_project_path, projekt_name)

    # Falls Unterordner nicht existiert -> erstellen
    if not os.path.exists(project_path):
        os.makedirs(project_path)

    # Sicherheitscheck: existiert das Basisverzeichnis wirklich?
    if projekt_verzeichnis not in get_directories(base_dir):
        return jsonify({'success': False}), 400

    # Projekt in DB finden
    project = Project.query.filter_by(path=base_project_path).first()

    # Zeitstempel aktualisieren
    if project:
        project.last_opened_at = datetime.utcnow()
        db.session.commit()

    return jsonify({'success': True})


# Teilnehmer eines Projekts abrufen
@verzeichnis_bp.route("/api/participants/<int:project_id>")
def get_participants_by_project(project_id):
    participants = Participant.query.filter_by(
        project_id=project_id
    ).all()

    return jsonify([p.to_dict() for p in participants])


# Synchronisiert, ob Projektordner noch existieren
def sync_project_availability():
    projects = Project.query.all()

    for project in projects:
        exists = os.path.isdir(project.path)  # Prüft Ordner im Dateisystem

        # Falls Status sich geändert hat -> aktualisieren
        if project.available != exists:
            project.available = exists

    db.session.commit()


# Datei-Upload API
@verzeichnis_bp.route("/api/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")  # Mehrere Dateien
    paths = request.form.getlist("paths")   # Zielpfade relativ
    project_id = request.form.get("project_id")

    project = Project.query.get(project_id)
    base_path = project.path

    # Dateien speichern
    for file, rel_path in zip(files, paths):
        rel_path = rel_path if rel_path else file.filename
        full_path = os.path.join(base_path, rel_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)  # Ordner erstellen
        file.save(full_path)  # Datei speichern

    return jsonify({"success": True})


# Teilnehmer löschen
@verzeichnis_bp.route("/api/participant/<int:participant_id>", methods=["DELETE"])
def delete_participant(participant_id):
    participant = Participant.query.get(participant_id)

    # Falls Ordner existiert -> löschen
    if participant.path and os.path.exists(participant.path):
        import shutil
        shutil.rmtree(participant.path)

    db.session.delete(participant)  # DB-Eintrag löschen
    db.session.commit()

    return jsonify({"success": True})


# Teilnehmer erstellen
@verzeichnis_bp.route("/api/participant/create", methods=["POST"])
@cross_origin()  # Erlaubt Cross-Origin speziell für diese Route
def create_participant():
    data = request.get_json()  # JSON-Daten empfangen

    name = data.get("name", "").strip()
    project_id = data.get("project_id")

    project = Project.query.get(project_id)
    participant_path = os.path.join(project.path, name)

    # Prüfen ob Teilnehmer schon existiert
    if os.path.exists(participant_path):
        return jsonify({"error": "existiert"}), 400

    os.makedirs(participant_path)  # Ordner erstellen

    # Teilnehmer-Objekt erstellen
    new_participant = Participant(
        name=name,
        path=participant_path,
        runs=0,
        last_run=None,
        project_id=project.id
    )

    db.session.add(new_participant)
    db.session.commit()

    return jsonify({
        "success": True,
        "participant": new_participant.to_dict()
    })