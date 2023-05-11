import logging
from django.db import transaction
from peddleconcept.models import Person, Area, Roster
from django.contrib import messages

from peddleconcept.deputy_api import DeputyAPI
from peddleconcept.models import ChangeLog

logger = logging.getLogger(__name__)

def sync_deputy_areas():
    """
    Synchronise Area/OperationalUnit objects between Local DB and Deputy API.
    Two way sync works as follows. At the start of sync & during sync:
    - state of local DB rows vs remote rows is tracked via source_row_state
    - locally added rows are SRS=pending => add to remote
    - locally 'deleted' rows are SRS=deleted => delete from remote
    - rows which exist both locally and remotely will have matching source_row_id and SRS=live
     => differences are resolved by using values from row with latest Modified timestamp
    - remotely deleted rows are marked in local DB as SRS=deleted
    - remotely added rows are added to local DB with SRS=live

    PS: don't actually delete any rows from Deputy!
    """
    api = DeputyAPI()

    db_areas = {
        area.source_row_id: area
        for area in Area.objects.filter(source='deputy', deputy_sync_enabled=True)
    }

    deputy_areas = {
        area.source_row_id: area
        for area in api.query_all_areas()
    }

    db_areas_set = set((srid for srid, area in db_areas.items() if area.source_row_state == 'live'))
    dpt_areas_set = set(deputy_areas.keys())

    matches_set = db_areas_set & dpt_areas_set
    del_dpt_set = db_areas_set - dpt_areas_set
    new_dpt_set = dpt_areas_set - db_areas_set
    logger.debug('matches=%s del=%s new=%s' % (matches_set, del_dpt_set, new_dpt_set))
    changelogs = []
    to_update_deputy = []

    with transaction.atomic():
        # update matched rows
        for srid in matches_set:
            db_row = db_areas[srid]
            dpt_row = deputy_areas[srid]
            if db_row.updated > dpt_row.updated:
                # local DB row is newer: push local changes to Deputy
                if (chglog := db_row.mark_update_pushed(dpt_row)):
                    changelogs.append(chglog)
                    to_update_deputy.append(db_row)
            else:
                if (chglog := db_row.update_from_instance(dpt_row)):
                    changelogs.append(chglog)
                db_row.save()

        # propagate deletions from deputy to local DB
        for srid in del_dpt_set:
            db_row = db_areas[srid]
            if (chglog := db_row.mark_source_deleted()):
                changelogs.append(chglog)
                db_row.save()
        
        # propagate added rows from deputy to local DB
        for srid in new_dpt_set:
            new_row = deputy_areas[srid]
            if (chglog := new_row.mark_source_added()):
                changelogs.append(chglog)
                new_row.save()
            
        ChangeLog.objects.bulk_create(changelogs)

    # now add new rows to Deputy and update changed rows
    if to_update_deputy:
        logger.debug('Update areas in deputy: ' + ', '.join((
            '[%s %d] %s' % (area.source_row_id, area.pk, area.name) for area in to_update_deputy)))
        api.update_areas(to_update_deputy)
    else:
        logger.info('No areas to update in Deputy')

    logger.info('sync_deputy_areas: %d matches, %d deleted remotely, %d updated/pushed, %d new rows' % (
        len(matches_set), len(del_dpt_set), len(to_update_deputy), len(new_dpt_set)
    ))