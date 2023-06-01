import logging
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from peddleconcept.models import Area, Person, Roster

logger = logging.getLogger(__name__)

def parse_datetime(timestamp):
    return make_aware(datetime.fromtimestamp(timestamp))

def parse_time_seconds(isodatetime):
    ts = datetime.fromisoformat(isodatetime)
    return ts.hour * 3600 + ts.minute * 60 + ts.second

def parse_datetime_str(isodatetime):
    return datetime.fromisoformat(isodatetime)

def parse_operationalunit_json(data):
    """
    Parse JSON blob representing Deputy API OperationalUnit and return Area model instance.
    See https://developer.deputy.com/deputy-docs/docs/operational-unit-1
    """
    return Area(
        source = 'deputy',
        source_row_state = 'live',
        source_row_id = str(data.get('Id')),

        area_name = data.get('OperationalUnitName'),
        colour = data.get('Colour'),
        sort_order = data.get('RosterSortOrder') or 0,
        updated = parse_datetime_str(data.get('Modified')),
        deputy_sync_enabled = True,
    )

def make_operationalunit_json(area, company_id):
    data = {
        "OperationalUnitName": area.area_name,
        "Company": company_id,
        "RosterSortOrder": area.sort_order,
        "Colour": area.colour or None,
    }

    if area.source_row_id:
        data['Id'] = int(area.source_row_id)
    else:
        data['Active'] = True
        data['ShowOnRoster'] = True
    return data

def parse_employee_json(data):
    """
    Parse JSON Employee data (from supervise API)
    See https://developer.deputy.com/deputy-docs/reference/getdetailsforallemployees
    """
    person = Person(
        source = 'deputy',
        source_row_state = 'live',
        source_row_id = str(data.get('Id')),

        first_name = data.get('FirstName'),
        last_name = data.get('LastName'),
        display_name = data.get('DisplayName'),
        active = bool(data.get('Active')),
        phone = data.get('Mobile') or None,
        email = data.get('Email') or None,
        updated = parse_datetime_str(data.get('Modified')),
    )
    person.active_deputy = data.get('Active') == True and data.get('Status') != 0 and data.get('AllowLogin') == True
    return person

def parse_roster_json(data, people={}, areas={}):
    """ Parse Roster JSON: https://developer.deputy.com/deputy-docs/docs/roster """
    rest_break_total = 0
    for slot in data.get('Slots', []):
        if slot.get('strTypeName') == 'Meal Break':
            continue
        slot_time = slot.get('intEnd', 0) - slot.get('intStart', 0)
        rest_break_total += max(slot_time, 0) // 60

    return Roster(
        source = 'deputy',
        source_row_state = 'live',
        source_row_id = data.get('Id'),

        person = people.get(data.get('Employee')),
        area = areas.get(data.get('OperationalUnit')),
        time_start = parse_datetime(data.get('StartTime')),
        time_end = parse_datetime(data.get('EndTime')),
        meal_break_mins = (parse_time_seconds(data.get('Mealbreak', 0)) // 60) or 0,
        rest_break_mins = rest_break_total or 0,
        open_shift = data.get('Open') or False,
        warning = data.get('Warning') or '',
        warning_override = data.get('WarningOverrideComment') or '',
        published = data.get('Published') or False,
        shift_notes = data.get('Comment') or '',
        shift_confirmed = data.get('ConfirmStatus') in (0, 2), # confirmation not required, or confirmed
        updated = parse_datetime_str(data.get('Modified')),
    )