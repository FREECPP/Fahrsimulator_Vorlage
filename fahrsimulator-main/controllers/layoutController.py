import logging
from flask import Blueprint, request, jsonify
from extensions import db
from dbModels.dashboardLayoutDB import dashboardLayout
from dbModels.projectAndParticipantsDB import Project


# -------------------------------
# Logging
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------
# Blueprint
# -------------------------------
layout_bp = Blueprint("layout", __name__, url_prefix="/api")


# -------------------------------
# 🔥 Alle Layouts (projektübergreifend)
# -------------------------------
@layout_bp.route("/layouts/full-db", methods=["GET"])
def get_full_layout_db():
    layouts = dashboardLayout.query.all()

    return jsonify([
        {
            "id": l.id,
            "name": l.name,
            "project_name": l.project.name,
            "layout": l.layout,
            "widgets": l.widgets
        }
        for l in layouts
    ])


# -------------------------------
# Layout CRUD (nur mit project_name)
# -------------------------------
@layout_bp.route("/layout/<project_name>/<layout_name>", methods=["GET", "POST", "DELETE"])
def handle_layout(project_name, layout_name):
    logger.info(f"Layout request: {request.method} | {project_name} | {layout_name}")

    project = Project.query.filter_by(name=project_name).first()

    if not project:
        logger.warning("Project not found")
        return jsonify({"error": "Project not found"}), 404

    # ---------------------------
    # POST (create / update)
    # ---------------------------
    if request.method == "POST":
        data = request.get_json() or {}

        layout_data = data.get("layout", [])
        widgets = data.get("widgets", [])

        try:
            # 🔥 nur projektgebunden prüfen (kein globaler Konflikt mehr)
            existing = dashboardLayout.query.filter_by(
                project_id=project.id,
                name=layout_name
            ).first()

            if existing:
                logger.info(f"Updating layout ID {existing.id}")
                existing.layout = layout_data
                existing.widgets = widgets
            else:
                logger.info("Creating new layout")

                new_layout = dashboardLayout(
                    name=layout_name,
                    layout=layout_data,
                    widgets=widgets,
                    project_id=project.id
                )
                db.session.add(new_layout)

            db.session.commit()
            return jsonify({"status": "saved"})

        except Exception as e:
            logger.error(f"Error saving layout: {e}")
            db.session.rollback()
            return jsonify({"error": "Interner Fehler"}), 500

    # ---------------------------
    # GET
    # ---------------------------
    if request.method == "GET":
        layout = dashboardLayout.query.filter_by(
            project_id=project.id,
            name=layout_name
        ).first()

        if not layout:
            return jsonify({
                "exists": False,
                "layout": [],
                "widgets": [],
                "project": project_name
            })

        return jsonify({
            "exists": True,
            "layout": layout.layout,
            "widgets": layout.widgets,
            "project": project_name
        })
    # ---------------------------
    # DELETE
    # ---------------------------
    if request.method == "DELETE":
        layout = dashboardLayout.query.filter_by(
            project_id=project.id,
            name=layout_name
        ).first()

        if not layout:
            return jsonify({"status": "not_found"}), 404

        try:
            db.session.delete(layout)
            db.session.commit()
            return jsonify({"status": "deleted"})

        except Exception as e:
            logger.error(f"Error deleting layout: {e}")
            db.session.rollback()
            return jsonify({"error": "Interner Fehler"}), 500


# -------------------------------
# Alle Layouts eines Projekts
# -------------------------------
@layout_bp.route("/layouts/<project_name>", methods=["GET"])
def get_layouts(project_name):
    project = Project.query.filter_by(name=project_name).first()

    if not project:
        return jsonify([])

    layouts = dashboardLayout.query.filter_by(project_id=project.id).all()

    return jsonify([
        {"name": l.name}
        for l in layouts
    ])