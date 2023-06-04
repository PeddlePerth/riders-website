from django.conf import settings
from .models import Settings

# Rezdy scraper settings
REZDY_LOGIN_SETTING = 'rezdy_login'
REZDY_COOKIES_SETTING = 'rezdy_cookies'

REZDY_NOTES_FIELDS = ('extras', 'order-special-requirements', 'order-internal-notes')
# only care about changes to these fields, which are also updated directly from Rezdy
REZDY_UPDATE_FIELDS = (
    'time_start', 'time_end', 'tour_type', 'tour_date', 
    'pickup_location', 'customer_name', 'customer_contact', 'quantity',
    'session',
)

FRINGE_LOGIN_SETTING = 'fringe_login'
FRINGE_COOKIES_SETTING = 'fringe_cookies'

FRINGE_UPDATE_FIELDS = (
    'time_start', 'time_end', 'tour_date', 'tour_type',
    'pickup_location', 'customer_name', 'quantity', 'pax',
)

TOUR_PAY_SETTING = 'tour_pay_config'
AUTO_UPDATE_SETTING = 'auto_update_config'
AUTO_UPDATE_STATUS = 'auto_update_state'
BIKES_SETTING = 'bike_types'

VENUES_PRESETS_SETTING = 'venues_presets'
ROSTER_GENERAL_SETTINGS = 'roster_settings'

AVAILABILITY_DEFAULT_WEEK_SETTING = 'availability_week_default'

DEPUTY_API_SETTING = 'deputy_api'

RIDER_PAYRATE_SETTING = 'rider_pay_rates'

def get_setting_or_default(setting_name, default):
    try:
        s = Settings.objects.get(name=setting_name)
    except Settings.DoesNotExist:
        s = Settings(name=setting_name, data=default)
        s.save()
    
    return s.data

def get_roster_setup_time():
    return get_setting_or_default(ROSTER_GENERAL_SETTINGS, {
        'setup_time_WH_minutes': 45,
    })

def get_login_setting(setting_name):
    return get_setting_or_default(setting_name, {
        'login': {
            'username': '',
            'password': '',
        },
    })

def get_bikes_setting():
    return get_setting_or_default(BIKES_SETTING, {
        'bike' : {
            'name': 'Std Bike',
            'num_passengers': 2,
            'quantity': 16,
            'default': True,
        },
        'rolls': {
            'name': 'Rolls',
            'num_passengers': 3,
            'quantity': 1,
        },
        'ebike': {
            'name': 'eBike',
            'num_passengers': 5,
            'quantity': 3,
        },
    })

def get_venues_presets():
    return get_setting_or_default(VENUES_PRESETS_SETTING, {
        'Bar Tour (2h)': [
            { 'type': 'transit', 'duration': 15 },
            { 'type': 'venue', 'duration': 30 },
            { 'type': 'transit', 'duration': 15 },
            { 'type': 'venue', 'duration': 30 },
            { 'type': 'transit', 'duration': 15 },
            { 'type': 'venue', 'duration': 15 },
        ],
        'Bar & Scav (3h)': [
            { 'type': 'transit', 'duration': 15 },
            { 'type': 'venue', 'duration': 30 },
            { 'type': 'transit', 'duration': 15 },
            { 'type': 'venue', 'duration': 30 },
            { 'type': 'activity', 'duration': 60, 'notes': 'proceed to Russell Square for ## RATED Scav' },
            { 'type': 'transit', 'duration': 15, 'notes': 'Finish Scav @ Russell, tally & present prize' },
            { 'type': 'venue', 'duration': 15 },
        ],
        'Half Bar/Scav (2h)': [
            { 'type': 'transit', 'duration': 15 },
            { 'type': 'venue', 'duration': 30 },
            { 'type': 'activity', 'duration': 45, 'notes': 'proceed to Russell Square for ## RATED Scav' },
            { 'type': 'transit', 'duration': 15, 'notes': 'Finish Scav @ Russell, tally & present prize' },
            { 'type': 'venue', 'duration': 15 },
        ],
    })
    """
    3:00pm - Tour start
    3:15pm - Arrive Market Grounds [NO SPECIAL]
    3:45pm - Leave MG
    4:00pm - Arrive Tiki AF [$10 Rum Punch]
    4:30pm - Leave Tiki, proceed to Russell to start scav
    5:30pm - Finish scav @ Russell
    5:45pm - Arrive Planet Royale [$12 Tap cocktail]
    6:00pm - Tour finish, thanks legends

    Requested X rated, bring G and X and confirm with Kelly
    Pickled Hering Restaurant
    """

def get_auto_update_setting():
    return get_setting_or_default(AUTO_UPDATE_SETTING, {
        'auto_update_rezdy': True,
        'auto_update_fringe': False,
        'scan_days_ahead': 7,
        'scan_days_behind': 0,
        'update_interval_minutes': 15,
    })

def get_deputy_api_setting():
    return get_setting_or_default(DEPUTY_API_SETTING, {
        'endpoint_url': 'https://{install}.{geo}.deputy.com',
        'auth_token': '',
        'default_company_id': 1,
        'default_employee_role_id': 50, # corresponds to "Employee" in our Deputy setup
    })

def get_rider_payrate_setting():
    return get_setting_or_default(RIDER_PAYRATE_SETTING, {
        '00_rider_probationary': 25,
        '10_rider_standard': 30,
        '20_rider_senior': 33,
        '30_rider_professional': 36,
    })

def get_setting(setting_name):
    try:
        return Settings.objects.get(name=setting_name).data
    except Settings.DoesNotExist:
        return None

def set_setting(setting_name, data):
    Settings.objects.update_or_create(name=setting_name, defaults={'name': setting_name, 'data': data})
