import os
import logging
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify
from flask_cors import cross_origin, CORS

from extensions import db
from utils.verzeichnis_utils import (
    init_base_dir,
    get_directories,
    validate_name,
    directory_exists,
    create_directory
)

from dbModels.projectAndParticipantsDB import Project, Participant


# -------------------------------
# Logging (weniger Debug-Spam)
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------
# Blueprint
# -------------------------------
verzeichnis_bp = Blueprint(
    'verzeichnis',
    __name__,
    url_prefix='/',
    template_folder='../templates'
)

CORS(verzeichnis_bp)

base_dir = init_base_dir()
project_path = None


# -------------------------------
# Startseite
# -------------------------------
@verzeichnis_bp.route('/')
def index():
    directories = get_directories(base_dir)
    return render_template('index.html', directories=directories)


# -------------------------------
# API: Verzeichnisse
# -------------------------------
@verzeichnis_bp.route('/api/verzeichnisse', methods=['GET'])
def get_dirs():
    return jsonify(get_directories(base_dir))


# -------------------------------
# API: Projekte
# -------------------------------
@verzeichnis_bp.route('/api/projects', methods=['GET'])
def get_projects():
    sync_project_availability()
    projects = Project.query.all()
    return jsonify([p.to_dict() for p in projects])


# -------------------------------
# 🔥 NEU: komplette Datenbank
# -------------------------------
@verzeichnis_bp.route('/api/full-db', methods=['GET'])
def get_full_db():
    projects = Project.query.all()

    result = []

    for project in projects:
        participants = Participant.query.filter_by(project_id=project.id).all()

        result.append({
            "project": project.to_dict(),
            "participants": [p.to_dict() for p in participants]
        })

    return jsonify(result)


# -------------------------------
# Verzeichnis erstellen
# -------------------------------
@verzeichnis_bp.route('/vz_anlegen', methods=['POST'])
def create():
    verzeichnis = request.form.get('projektverzeichnis', '').strip()
    creator = request.form.get('creator', 'Unbekannt')

    if not validate_name(verzeichnis):
        return jsonify({'success': False}), 400

    existing = Project.query.filter_by(name=verzeichnis).first()
    if existing:
        return jsonify({'success': False, 'message': 'existiert schon'}), 400

    try:
        full_path = os.path.join(base_dir, verzeichnis)
        create_directory(base_dir, verzeichnis)

        creator = request.form.get('creator')
        if not creator:
            creator = "Unbekannt"

        new_project = Project(
            name=verzeichnis,
            path=full_path,
            creator=creator
        )

        db.session.add(new_project)
        db.session.commit()

        logger.info(f"Projekt erstellt: {verzeichnis}")

        return jsonify({
            'success': True,
            'project': new_project.to_dict()
        })

    except Exception as e:
        logger.error(f"Fehler beim Erstellen: {e}")
        db.session.rollback()
        return jsonify({'error': 'Interner Fehler'}), 500


# -------------------------------
# Projekt auswählen
# -------------------------------
@verzeichnis_bp.route('/vz_select', methods=['POST'])
def select():
    global project_path

    projekt_verzeichnis = request.form.get('existierendesVerzeichnis', '').strip()
    projekt_name = request.form.get('projektname', '').strip()

    base_project_path = os.path.join(base_dir, projekt_verzeichnis)
    project_path = os.path.join(base_project_path, projekt_name)

    if not os.path.exists(project_path):
        os.makedirs(project_path)

    if projekt_verzeichnis not in get_directories(base_dir):
        return jsonify({'success': False}), 400

    project = Project.query.filter_by(path=base_project_path).first()

    if project:
        project.last_opened_at = datetime.utcnow()
        db.session.commit()

    return jsonify({'success': True})


# -------------------------------
# Teilnehmer abrufen
# -------------------------------
@verzeichnis_bp.route("/api/participants/<int:project_id>")
def get_participants_by_project(project_id):
    participants = Participant.query.filter_by(
        project_id=project_id
    ).all()

    return jsonify([p.to_dict() for p in participants])


# -------------------------------
# Sync Projektstatus
# -------------------------------
def sync_project_availability():
    projects = Project.query.all()

    for project in projects:
        exists = os.path.isdir(project.path)

        if project.available != exists:
            project.available = exists

    db.session.commit()


# -------------------------------
# Upload
# -------------------------------
@verzeichnis_bp.route("/api/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    paths = request.form.getlist("paths")
    project_id = request.form.get("project_id")

    project = db.session.get(Project, project_id)

    if not project:
        return jsonify({"error": "Projekt nicht gefunden"}), 404

    base_path = project.path

    for file, rel_path in zip(files, paths):
        rel_path = rel_path if rel_path else file.filename
        full_path = os.path.join(base_path, rel_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        file.save(full_path)

    return jsonify({"success": True})


# -------------------------------
# Teilnehmer löschen
# -------------------------------
@verzeichnis_bp.route("/api/participant/<int:participant_id>", methods=["DELETE"])
def delete_participant(participant_id):
    participant = db.session.get(Participant, participant_id)

    if not participant:
        return jsonify({"error": "Nicht gefunden"}), 404

    if participant.path and os.path.exists(participant.path):
        import shutil
        shutil.rmtree(participant.path)

    db.session.delete(participant)
    db.session.commit()

    return jsonify({"success": True})


# -------------------------------
# Teilnehmer erstellen
# -------------------------------
@verzeichnis_bp.route("/api/participant/create", methods=["POST"])
@cross_origin()
def create_participant():
    data = request.get_json()

    name = data.get("name", "").strip()
    project_id = data.get("project_id")

    project = db.session.get(Project, project_id)

    if not project:
        return jsonify({"error": "Projekt nicht gefunden"}), 404

    participant_path = os.path.join(project.path, name)

    if os.path.exists(participant_path):
        return jsonify({"error": "existiert"}), 400

    os.makedirs(participant_path)

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