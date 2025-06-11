import os
import requests
from flask import Blueprint, jsonify
import teslapy

bp = Blueprint('tesla_api', __name__)

TESLA_EMAIL = os.environ.get('TESLA_EMAIL')
TESLA_PASSWORD = os.environ.get('TESLA_PASSWORD')


def _find_vehicle(tesla: teslapy.Tesla, vehicle_id: str):
    """Return vehicle by id string or None."""
    for vehicle in tesla.vehicle_list():
        if str(vehicle.get('id_s')) == str(vehicle_id):
            return vehicle
    return None


def get_vehicle_data(vehicle_id: str):
    """Return vehicle data or raise for unexpected errors."""
    if not (TESLA_EMAIL and TESLA_PASSWORD):
        raise RuntimeError('TESLA_EMAIL and TESLA_PASSWORD not configured')
    with teslapy.Tesla(TESLA_EMAIL, TESLA_PASSWORD) as tesla:
        vehicle = _find_vehicle(tesla, vehicle_id)
        if vehicle is None:
            raise ValueError('Vehicle not found')
        try:
            return vehicle.get_vehicle_data()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 408:
                # Vehicle offline, try wake up once
                try:
                    vehicle.sync_wake_up()
                    return vehicle.get_vehicle_data()
                except requests.exceptions.HTTPError:
                    raise
            raise


@bp.route('/api/data/<vehicle_id>')
def api_data_vehicle(vehicle_id):
    """Return vehicle data as JSON or an error message."""
    try:
        data = get_vehicle_data(vehicle_id)
        return jsonify(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 500
        if status == 408:
            return jsonify({'error': 'vehicle offline'}), 503
        return jsonify({'error': 'failed to fetch vehicle data'}), status
    except Exception:
        return jsonify({'error': 'unexpected error'}), 500
