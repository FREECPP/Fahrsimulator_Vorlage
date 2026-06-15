import os

from flask import Blueprint, jsonify
from flask_cors import CORS

silab_bp = Blueprint(
    "silab",
    __name__,
    url_prefix="/api/silab"
)

CORS(silab_bp)

#SIMULATION_DIR = r"A:\SILAB\Simulationen" #TODO
SIMULATION_DIR = r"D:\SILAB\Projects\SILABDemo"

@silab_bp.route(
    "/simulations",
    methods=["GET"]
)
def get_simulations():

    if not os.path.exists(SIMULATION_DIR):
        return jsonify([])

    simulations = []

    for item in os.listdir(SIMULATION_DIR):

        full_path = os.path.join(
            SIMULATION_DIR,
            item
        )

        if os.path.isfile(full_path) and item.endswith(".cfg"):
            simulations.append({
                "name": item,
                "path": full_path
            })

    simulations.sort(
        key=lambda x: x["name"].lower()
    )

    return jsonify(simulations)