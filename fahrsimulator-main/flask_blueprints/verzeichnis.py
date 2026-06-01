import os
from flask import Blueprint, render_template, request, jsonify
from utils.verzeichnis_utils import (
    init_base_dir,
    get_directories,
    validate_name,
    directory_exists,
    create_directory
)

verzeichnis_bp = Blueprint(
    'verzeichnis',
    __name__,
    url_prefix='/',
    template_folder='../templates'
)

base_dir = init_base_dir()
project_path = None

@verzeichnis_bp.route('/')
def index():
    directories = get_directories(base_dir)
    return render_template('index.html', directories=directories)


@verzeichnis_bp.route('/api/verzeichnisse', methods=['GET'])
def get_dirs():
    return jsonify(get_directories(base_dir))


@verzeichnis_bp.route('/vz_anlegen', methods=['POST'])
def create():
    verzeichnis = request.form.get('projektverzeichnis', '').strip()

    if not validate_name(verzeichnis):
        return jsonify({'success': False, 'message': 'Ungültige Eingabe'}), 400

    if directory_exists(base_dir, verzeichnis):
        return jsonify({'success': False, 'message': f'"{verzeichnis}" existiert bereits'}), 400

    try:
        create_directory(base_dir, verzeichnis)
        return jsonify({'success': True, 'message': f'"{verzeichnis}" erstellt', 'name': verzeichnis})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Fehler: {str(e)}'}), 500


@verzeichnis_bp.route('/vz_select', methods=['POST'])
def select():
    global project_path
    projekt_verzeichnis = request.form.get('existierendesVerzeichnis', '').strip()
    projekt_name = request.form.get('projektname', '').strip()
    
    #projekt_pfad = base_dir+projekt_verzeichnis + "\\" + projekt_name
    project_path = os.path.join(base_dir, projekt_verzeichnis, projekt_name)
    
    if directory_exists(base_dir, project_path):
        return jsonify({'success': False, 'message': f'"{project_path}" existiert bereits'}), 400
    else:
        os.makedirs(project_path)
    print("selected: ", project_path)
    
    if projekt_verzeichnis not in get_directories(base_dir):
        return jsonify({'success': False, 'message': 'Nicht gefunden'}), 400

    return jsonify({'success': True, 'message': f'"{projekt_verzeichnis}" ausgewählt', 'name': projekt_verzeichnis})
