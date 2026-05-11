from datetime import datetime
from extensions import db

import os

# ===== Project =====
class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)
    path = db.Column(db.String(500), nullable=False, unique=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_opened_at = db.Column(db.DateTime, nullable=True)

    creator = db.Column(db.String(100), nullable=False)

    available = db.Column(db.Boolean, default=True)

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
            "created_at":
                self.created_at.isoformat()
                if self.created_at else None,

            "last_opened_at":
                self.last_opened_at.isoformat()
                if self.last_opened_at else None,

            "creator": self.creator,
            "available": self.available
        }

# ===== Participant =====
class Participant(db.Model):
    __tablename__ = "participant"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)

    path = db.Column(db.String(500), nullable=False)

    run_started_at = db.Column(db.DateTime, nullable=True)
    run_ended_at = db.Column(db.DateTime, nullable=True)

    run_duration_seconds = db.Column(db.Integer, nullable=True)

    file_size_bytes = db.Column(
        db.BigInteger,
        nullable=True,
        default=0
    )

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("project.id"),
        nullable=False
    )

    project = db.relationship(
        "Project",
        back_populates="participants"
    )

    # ===== Folder Size =====
    def calculate_folder_size(self):
        total_size = 0

        if not self.path or not os.path.exists(self.path):
            return 0

        for dirpath, dirnames, filenames in os.walk(self.path):

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)

                try:
                    total_size += os.path.getsize(filepath)

                except Exception:
                    pass

        return total_size

    # ===== Size MB =====
    def get_size_mb(self):
        if not self.file_size_bytes:
            return 0

        return round(self.file_size_bytes / (1024 * 1024), 2)

    # ===== To Dict =====
    def to_dict(self):
        current_size = self.calculate_folder_size()

        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,

            "run_started_at":
                self.run_started_at.isoformat()
                if self.run_started_at else None,

            "run_ended_at":
                self.run_ended_at.isoformat()
                if self.run_ended_at else None,

            "run_duration_seconds":
                self.run_duration_seconds,

            "file_size":
                current_size,

            "project":
                self.project.name
                if self.project else None
        }