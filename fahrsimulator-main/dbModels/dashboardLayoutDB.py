from extensions import db
from sqlalchemy import JSON


class dashboardLayout(db.Model):
    __tablename__ = "dashboard_layout"
    __table_args__ = (
        db.UniqueConstraint(
            "project_id",
            "name",
            name="uq_project_layout"
        ),
    )
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False)  # Layout-Name (z.B. "Default", "Test1")

    layout = db.Column(JSON)
    widgets = db.Column(JSON)

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("project.id"),
        nullable=False
    )

    project = db.relationship("Project", backref="layouts")