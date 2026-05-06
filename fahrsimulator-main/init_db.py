import os
import shutil

from flask_app import app
from extensions import db

# 🔥 WICHTIG: ALLE Models importieren!
from dbModels.projectAndParticipantsDB import Project, Participant
from dbModels.dashboardLayoutDB import dashboardLayout

# 👉 dein Base-Verzeichnis (anpassen!)
BASE_DIR = "C:\\Fahrsimulator_Projekte\\"


def delete_project_folders():
    if os.path.exists(BASE_DIR):
        print("🗑 Lösche Projektordner...")
        shutil.rmtree(BASE_DIR)

    os.makedirs(BASE_DIR, exist_ok=True)
    print("📁 Ordner neu erstellt")


with app.app_context():
    print("⚠️ Dropping all tables...")
    db.drop_all()

    print("🔧 Creating all tables...")
    db.create_all()

    # 🔥 Optional: Filesystem reset
    delete_project_folders()

    print("✅ ALLES komplett zurückgesetzt")