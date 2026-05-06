from datetime import datetime
from extensions import db


# 📁 Project Model
class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)
    path = db.Column(db.String(500), nullable=False, unique=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_opened_at = db.Column(db.DateTime, nullable=True)

    creator = db.Column(db.String(100), nullable=False)

    # Ob Ordner aktuell existiert (z.B. beim Scan geprüft)
    available = db.Column(db.Boolean, default=True)

    # 🔗 1:n Beziehung zu Probanden
    participants = db.relationship(
        "Participant",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_opened_at": self.last_opened_at.isoformat() if self.last_opened_at else None,
            "creator": self.creator,
            "available": self.available
        }


# 👤 Participant Model
class Participant(db.Model):
    __tablename__ = "participant"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)

    # 📁 Pfad relativ oder absolut (je nach Design)
    path = db.Column(db.String(500), nullable=False)

    runs = db.Column(db.Integer, default=0)
    last_run = db.Column(db.DateTime, nullable=True)

    # 🔗 Fremdschlüssel → genau EIN Projekt
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("project.id"),
        nullable=False
    )

    project = db.relationship("Project", back_populates="participants")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "runs": self.runs,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "project": self.project.name if self.project else None
        }