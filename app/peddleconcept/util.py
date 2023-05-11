from datetime import datetime, time, date, timedelta
from django.forms import model_to_dict
from django.utils.timezone import (
    localtime, localdate, make_aware, is_aware, get_default_timezone, now
)
from urllib.parse import urlparse
from django.utils.html import escape
from django.utils.safestring import mark_safe

from django.db import transaction, models
from django.conf import settings
import math
import logging
from html import unescape

logger = logging.getLogger(__name__)

def apply_colmap(colmap, row):
    return {
        dest_field: row[src_field] for dest_field, src_field in colmap.items()
    }

def get_time(dateortime):
    if isinstance(dateortime, datetime):
        t = dateortime.time()
    #elif isinstance(dateortime, str):
    #    t = parse(dateortime, dayfirst=True).time()
    else:
        t = dateortime
    return t

def format_time(t):
    return localtime(t).strftime("%I:%M%p").lower().strip('0')

def format_timedelta(td):
    hours = int(td.seconds / 3600)
    minutes = int((td.seconds % 3600) / 60)
    if hours == 0:
        return "%dm" % minutes
    elif minutes == 0:
        return "%dh" % hours
    else:
        return "%dh %dm" % (hours, minutes)

def json_datetime(dt):
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, time())
    millis = (dt.timestamp() * 1000)
    return int(millis)

def from_json_datetime(millis):
    if not millis and millis != 0:
        return None
    return datetime.fromtimestamp(float(millis) / 1000)

def from_json_date(millis):
    return make_aware(from_json_datetime(millis)).date()

def format_date(dt):
    if isinstance(dt, datetime):
        if not is_aware(dt):
            dt = make_aware(dt)
        return localtime(dt).strftime('%I:%M%p %a %d/%m/%Y')
    else:
        return dt.strftime('%a %d/%m/%Y')

def add_days(dt, days):
    return (datetime.combine(dt, time()) + timedelta(days=days)).date()

def start_of_week(dt):
    # get the first day of the week
    return add_days(dt, -dt.weekday())

# from https://stackoverflow.com/questions/3806473/python-week-number-of-the-month
def week_of_month(dt):
    """ Returns the week of the month for the specified date.
    """

    first_day = dt.replace(day=1)

    dom = dt.day
    adjusted_dom = dom + first_day.weekday()

    return int(ceil(adjusted_dom/7.0))

def get_model_fields(model):
    if isinstance(model, type):
        model_class = model
    else:
        model_class = type(model)
    
    return [f.name for f in model_class._meta.fields]

def diff_model_instances(row1, row2, fields=None, exclude=[]):
    if fields is None:
        fields = get_model_fields(row1)

    changes = {}
        
    for f in fields:
        if f in exclude or f == 'id':
            # automatically ignore primary key
            continue

        a = getattr(row1, f, None)
        b = getattr(row2, f, None)
        if a != b:
            if isinstance(a, models.Model) and isinstance(b, models.Model) and a.pk == b.pk:
                continue
            changes[f] = (a, b)

    return changes

def match_id_lists(new_ids, old_ids):
    new_ids = set(new_ids)
    old_ids = set(old_ids)

    added = new_ids - old_ids # set difference
    deleted = old_ids - new_ids
    unchanged = new_ids & old_ids # set intersection
    return added, deleted, unchanged

def match_and_compare_rows(new_rows, old_rows, key, fields=None, ignore_fields=[], exclude_fields=[]):
    # construct a dict of existing rows indexed by the key column
    # this looks the same as the output of QuerySet.in_bulk()
    old_data = { getattr(r, key): r for r in old_rows }
    new_data = { getattr(r, key): r for r in new_rows }
    
    # store changed rows in a dict row_id:(old_instance, new_instance, diff)
    rows_changed = {}
    rows_changes_ignored = {}

    # added, deleted rows are in a dict row_key:instance
    rows_added = {}
    rows_deleted = {}

    # unchanged rows are in a dict of row_id: (old_instance, new_instance)
    rows_unchanged = {}
    for row_id in new_data.keys():

        if row_id in old_data:
            # row already exists: check for any changes
            diff = diff_model_instances(old_data[row_id], new_data[row_id], fields=fields, exclude=exclude_fields)

            if diff:
                # check if the changes are to be ignored
                ignore = True
                for field_name in diff.keys():
                    if not field_name in ignore_fields:
                        ignore = False
                        break
                if ignore:
                    rows_changes_ignored[row_id] = (old_data[row_id], new_data[row_id], diff)
                else:
                    rows_changed[row_id] = (old_data[row_id], new_data[row_id], diff)
            else:
                rows_unchanged[row_id] = (old_data[row_id], new_data[row_id])
        else:
            # row has been added
            rows_added[row_id] = new_data[row_id]
    
    # check for deleted rows
    for row_id in old_data.keys():
        if not row_id in new_data:
            rows_deleted[row_id] = old_data[row_id]

    return rows_changed, rows_added, rows_deleted, rows_unchanged, rows_changes_ignored

def get_json_value(val):
    if isinstance(val, time):
        return val.isoformat()
    if isinstance(val, (date, datetime)):
        return json_datetime(val)
    if isinstance(val, models.Model):
        # record only related model primary key
        return val.pk
    return val

def get_text_value(val):
    if isinstance(val, (time, date, datetime)):
        return val.isoformat()
    if isinstance(val, models.Model):
        return "pk=%d: %s" % (val.pk, str(val))

def model_to_json(inst):
    return {
        field: get_json_value(val) for field, val in model_to_dict(inst).items() 
    }

def diff_to_json(chg):
    for f in chg.keys():
        old, new = chg[f]
        if isinstance(old, datetime):
            chg[f] = (localtime(old).isoformat(), localtime(new).isoformat())
        elif isinstance(old, (date, time)):
            chg[f] = (old.isoformat(), new.isoformat())
        elif isinstance(old, models.Model):
            # for foreign key fields: record the primary key only
            chg[f] = (old.pk, new.pk)
    return chg

def update_model_with_dict(model, dict, fields=None):
    for f, v in dict.items():
        if fields and not f in fields:
            continue
        setattr(model, f, v)

def html_unescape(txt):
    return unescape(txt.replace('<br>', '\n'))

def html_prepare(txt):
    return mark_safe(escape(txt.strip()).replace('\n', '<br>')) if txt else ''

def str_response(r, with_urlparams=settings.DEBUG):
    if with_urlparams:
        url = urlparse(r.url)
        url = url._replace(fragment='', query='')
        url_string = url.geturl()
    else: 
        url_string = r.url
    return "%s %s %s (Content-Type: %s, Length: %d)" % (r.request.method, r.status_code, url_string, r.headers['content-type'], len(r.content))

def log_response(r, log_content=False, logger=logger):
    if r.history:
        for i in range(len(r.history)):
            logger.debug("[%d] %s" % (i, str_response(r.history[i])))
    logger.debug(str_response(r))
    if log_content:
        if 'application/json' in r.headers['content-type']:
            logger.debug(json.dumps(r.json(), indent=4))
        logger.debug(r.content)

def try_parse_int(num):
    try:
        return int(num)
    except ValueError:
        return None

def start_of_day(date):
    return make_aware(datetime.combine(date, time(0, 0)))

def end_of_day(date):
    return make_aware(datetime.combine(date, time(23, 59, 59)))

def iterate_once_more(iterable, last_item):
    def my_iterator():
        for x in iterable:
            yield x
        yield last_item
    return my_iterator

def abbreviate(name):
    words = name.split(' ')
    if len(words) > 1:
        return "".join([n[0].upper() for n in name.split(' ')])
    else:
        return name

def get_date_filter(start_date, end_date, field):
    dt_start = datetime.combine(start_date, time(0, 0, 0), tzinfo=get_default_timezone())
    dt_end = datetime.combine(end_date, time(23, 59, 59), tzinfo=get_default_timezone())
    return {
        '%s__gte' % field: dt_start,
        '%s__lte' % field: dt_end,
    }

def get_iso_date(date_str=None):
    if not date_str:
        return localdate(now())
    else:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            pass
