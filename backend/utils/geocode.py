import urllib.request
import json
import logging
from typing import Dict, Any

log = logging.getLogger(__name__)

def reverse_geocode(lat: float, lon: float) -> Dict[str, Any]:
    """
    Reverse geocode latitude and longitude into city, state, country using OpenStreetMap Nominatim.
    Returns a dict containing 'city', 'state', 'country', and formatted 'location_str'.
    """
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
    headers = {
        "User-Agent": "CollarCheckChatbot/1.0 (contact@collarcheck.com)"
    }
    
    city = None
    state = None
    country = None
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                address = data.get("address", {})
                
                city = address.get("city") or address.get("town") or address.get("village") or address.get("suburb") or address.get("county") or address.get("state_district")
                state = address.get("state")
                country = address.get("country")
    except Exception as e:
        log.error(f"Error calling reverse geocoding service: {e}")
        
    parts = []
    if city:
        parts.append(str(city))
    if state:
        parts.append(str(state))
    if country:
        parts.append(str(country))
        
    location_str = ", ".join(parts) if parts else "Unknown Location"
    
    return {
        "city": city,
        "state": state,
        "country": country,
        "location_str": location_str
    }
