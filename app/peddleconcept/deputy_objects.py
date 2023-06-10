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
        display_name = data.get('OperationalUnitName'),
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
        email_verified = True,
        updated = parse_datetime_str(data.get('Modified')),
    )
    person.active_deputy = data.get('Active') == True and data.get('Status') != 0 and data.get('AllowLogin') == True
    return person

def parse_roster_json(data, employee_dict=None, area_dict=None, api_creator_id=None):
    employee_id = str(data.get('Employee'))
    ou_id = str(data.get('OperationalUnit'))

    roster = Roster(
        source = 'deputy',
        source_row_state = 'live',
        source_row_id = str(data.get('Id')),

        person = employee_dict.get(employee_id) if employee_dict and employee_id else None,
        area = area_dict.get(ou_id) if area_dict else None,
        time_start = parse_datetime(data.get('StartTime')),
        time_end = parse_datetime(data.get('EndTime')),
        open_shift = data.get('Open') or False,
        approval_required = data.get('ApprovalRequired') or False,
        warning_comment = data.get('Warning') or '',
        warning_override_comment = data.get('WarningOverrideComment') or '',
        published = data.get('Published') or False,
        shift_notes = data.get('Comment') or '',
        confirm_status = data.get('ConfirmStatus'),
        swap_status = data.get('SwapStatus'),
    )
    # extra attributes not stored in the DB
    roster.employee_id = employee_id
    roster.operationalunit_id = ou_id
    if isinstance(slots := data.get('Slots'), list):
        for slot in sorted(slots, key=lambda s: s.get('intStart')):
            if slot.get('blnEmptySlot') != False:
                continue
            roster.tour_slots.append({
                "type": "break",
                "time_start": slot.get('intUnixStart') * 1000, # store timestamps in Javascript format
                "time_end": slot.get('intUnixEnd') * 1000,
            })

    if (creator := data.get('Creator')) and creator == api_creator_id:
        roster._is_manual = False # created using the API account
    else:
        roster._is_manual = True # assume all other Roster objects are created manually
    return roster

def make_roster_json(roster):
    data = {
        'Id': roster.source_row_id if roster.source_row_id else None,
        'Employee': roster.person.source_row_id if roster.person and roster.person.source_row_id else None,
        'OperationalUnit': roster.area.source_row_id if roster.area and roster.area.source_row_id else None,
        'StartTime': int(roster.time_start.timestamp()),
        'EndTime': int(roster.time_end.timestamp()),
        'Open': roster.open_shift,
        'ApprovalRequired': roster.approval_required,
        'Warning': roster.warning_comment,
        'WarningOverrideComment': roster.warning_override_comment,
        'Published': roster.published,
        'Comment': roster.shift_notes,
        'ConfirmStatus': roster.confirm_status,
        'SwapStatus': roster.swap_status,
        'Slots': [
            {
                "blnEmptySlot": False,
                "strType": "B",
                "intUnixStart": slot['time_start'] // 1000,
                "intUnixEnd": slot['time_end'] // 1000,
                "strTypeName": "Meal Break" if i == 0 else "Rest Break",
            }
            for i, slot in enumerate(roster.tour_slots)
            if slot['type'] == 'break'
        ],
    }
    return data
