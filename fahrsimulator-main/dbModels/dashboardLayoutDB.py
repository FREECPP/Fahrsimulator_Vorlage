from extensions import db
from sqlalchemy import JSON


class dashboardLayout(db.Model):
    project_name = db.Column(db.String(255), primary_key=True)
    layout = db.Column(JSON)
    widgets = db.Column(JSON)

