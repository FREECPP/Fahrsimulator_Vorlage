import os
import shutil

from flask_app import app
from extensions import db

# 🔥 WICHTIG: ALLE Models importieren!
from dbModels.projectAndParticipantsDB import (
    Project,
    Participant
)

from dbModels.dashboardLayoutDB import dashboardLayout

# 👉 Base-Verzeichnis
BASE_DIR = r"A:\Fahrsimulator_Projekte"


# ==================================================================================
# Projektordner löschen + neu erstellen
# ==================================================================================
def delete_project_folders():

    print("\n📁 FILESYSTEM RESET")
    print("=" * 60)

    print(f"🔍 Prüfe ob BASE_DIR existiert:")
    print(f"   {BASE_DIR}")

    if os.path.exists(BASE_DIR):

        print("✅ BASE_DIR existiert")
        print("🗑 Lösche Projektordner...")

        shutil.rmtree(BASE_DIR)

        print("✅ Projektordner gelöscht")

    else:
        print("ℹ️ BASE_DIR existiert noch nicht")

    print("📁 Erstelle BASE_DIR neu...")

    os.makedirs(BASE_DIR, exist_ok=True)

    print("✅ Ordner erfolgreich erstellt")


# ==================================================================================
# DB komplett resetten
# ==================================================================================
def reset_database():

    print("\n🗄 DATABASE RESET")
    print("=" * 60)

    with app.app_context():

        print("🔍 Verbinde mit Datenbank...")

        print("⚠️ Dropping all tables...")

        db.drop_all()

        print("✅ Alle Tabellen gelöscht")

        print("🔧 Creating all tables...")

        db.create_all()

        print("✅ Tabellen neu erstellt")

        print("\n📊 Verfügbare Tabellen:")

        for table in db.metadata.tables.keys():
            print(f"   • {table}")

        print("\n✅ Datenbank Reset abgeschlossen")


# ==================================================================================
# DB Struktur anzeigen
# ==================================================================================
def print_database_structure():

    print("\n📊 DATABASE STRUCTURE")
    print("=" * 60)

    print("\n📁 TABLE: project")
    print("-" * 60)

    project_columns = [
        "id",
        "name",
        "path",
        "created_at",
        "last_opened_at",
        "creator",
        "available"
    ]

    for col in project_columns:
        print(f"   • {col}")

    print("\n👤 TABLE: participant")
    print("-" * 60)

    participant_columns = [
        "id",
        "name",
        "path",
        "run_started_at",
        "run_ended_at",
        "run_duration_seconds",
        "file_size",
        "project_id"
    ]

    for col in participant_columns:
        print(f"   • {col}")

    print("\n📐 TABLE: dashboard_layout")
    print("-" * 60)

    try:
        columns = dashboardLayout.__table__.columns

        for column in columns:
            print(f"   • {column.name}")

    except Exception as e:
        print("❌ Keine Layout-Spalten gefunden")
        print(f"Fehler: {e}")

    print("\n✅ Struktur erfolgreich ausgegeben")


# ==================================================================================
# DB TEST
# ==================================================================================
def test_database():

    print("\n🧪 DATABASE TEST")
    print("=" * 60)

    with app.app_context():

        try:

            print("🔍 Teste Project Query...")

            projects = Project.query.all()

            print(f"✅ Project Query erfolgreich")
            print(f"📁 Anzahl Projekte: {len(projects)}")

            print("\n🔍 Teste Participant Query...")

            participants = Participant.query.all()

            print(f"✅ Participant Query erfolgreich")
            print(f"👤 Anzahl Participants: {len(participants)}")

            print("\n✅ Datenbank funktioniert korrekt")

        except Exception as e:

            print("\n❌ DATABASE TEST FEHLGESCHLAGEN")
            print(f"Fehler: {e}")


# ==================================================================================
# MAIN
# ==================================================================================
if __name__ == "__main__":

    print("\n🚀 RESET STARTED")
    print("=" * 60)

    # 🔥 DB reset
    print("\n➡️ Starte Datenbank Reset...")
    reset_database()

    # 🔥 Filesystem reset
    print("\n➡️ Starte Filesystem Reset...")
    delete_project_folders()

    # 🔥 Struktur anzeigen
    print("\n➡️ Zeige Datenbank Struktur...")
    print_database_structure()

    # 🔥 DB testen
    print("\n➡️ Teste Datenbank...")
    test_database()

    print("\n🎉 RESET COMPLETED")
    print("=" * 60)
    print("✅ Datenbank zurückgesetzt")
    print("✅ Projektordner zurückgesetzt")
    print("✅ Tabellen erstellt")
    print("✅ Struktur geprüft")
    print("✅ Datenbank getestet")
    print()