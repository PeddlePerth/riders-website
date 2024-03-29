
from peddleconcept.models import Area, Tour
import logging
logger = logging.getLogger(__name__)

# Keep a cache of tour "pickup location" strings to Area IDs
tour_locations_cache = {}
tour_locations_keyword_cache = {}
tour_area_default = None

def load_areas_locations():
    global tour_locations_cache, tour_locations_keyword_cache, tour_area_default
    tour_locations_cache = {}
    tour_locations_keyword_cache = {}
    tour_area_default = None

    """ Load or reload the tour locations cache from the DB """
    for area in Area.objects.filter(active=True):
        for loc_exact in area.locations_list:
            tour_locations_cache[loc_exact] = area
        for loc_kw in area.locations_keywords:
            tour_locations_keyword_cache[loc_kw] = area
        if tour_area_default is None or area.sort_order < tour_area_default.sort_order:
            tour_area_default = area

def save_areas_locations():
    if not tour_locations_cache:
        return
    
    areas = {}
    for loc_exact, area in tour_locations_cache.items():
        if not area.id in areas:
            areas[area.id] = area
            area._loc_list = area.locations_list
        area = areas[area.id]
        if not loc_exact in area._loc_list:
            logger.info('Adding pickup location "%s" to area %s' % (loc_exact, area.name))
            area._loc_list.append(loc_exact)
    for area in areas.values():
        area.tour_locations = area.tour_locations if isinstance(area.tour_locations, dict) else {}
        area.tour_locations['pickup_locations_exact'] = area._loc_list
        area.tour_locations.setdefault('pickup_locations_keyword', [])
        area.save()

def get_tour_area(pickup_location):
    search_str = pickup_location.lower().strip()
    if not search_str:
        return tour_area_default

    if search_str in tour_locations_cache:
        return tour_locations_cache[search_str]
    for keyword, area in tour_locations_keyword_cache.items():
        if keyword in search_str:
            # update the exact match list
            tour_locations_cache[search_str] = area
            return area

    # also update the exact match list for default tours
    tour_locations_cache[search_str] = tour_area_default
    return tour_area_default

