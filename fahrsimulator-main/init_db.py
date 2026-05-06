from flask_app import app
from extensions import db
from dbModels.projectAndParticipantsDB import Project, Participant
from datetime import datetime

with app.app_context():
    db.create_all()

    # ❗ verhindert mehrfaches Seeding
    if Project.query.first():
        print("Daten existieren bereits – überspringe Seed.")
    else:
        # 📁 Projekte
        project_test = Project(
            name="Test",
            path=r"C:\Fahrsimulator_Projekte\Test",
            creator="Admin"
        )

        project_teststudie = Project(
            name="TestStudie",
            path=r"C:\Fahrsimulator_Projekte\TestStudie",
            creator="Admin"
        )

        db.session.add_all([project_test, project_teststudie])
        db.session.commit()  # wichtig für IDs!

        # 👤 Proband für "Test"
        p1 = Participant(
            name="Proband Test 1",
            path=r"C:\Fahrsimulator_Projekte\Test\Proband1",
            runs=5,
            last_run=datetime(2024, 1, 10),
            project_id=project_test.id
        )

        # 👤👤 Probanden für "TestStudie"
        p2 = Participant(
            name="Proband Studie 1",
            path=r"C:\Fahrsimulator_Projekte\TestStudie\Proband1",
            runs=10,
            last_run=datetime(2024, 2, 5),
            project_id=project_teststudie.id
        )

        p3 = Participant(
            name="Proband Studie 2",
            path=r"C:\Fahrsimulator_Projekte\TestStudie\Proband2",
            runs=3,
            last_run=datetime(2024, 3, 1),
            project_id=project_teststudie.id
        )

        # 💾 Speichern
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        print("✅ Testdaten korrekt eingefügt!")

    print("Datenbank bereit!")