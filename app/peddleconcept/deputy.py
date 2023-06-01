import logging
from django.db import transaction
from django.db.models import Q
from peddleconcept.models import Person, Area, Roster, ChangeLog
from django.contrib import messages

from peddleconcept.deputy_api import DeputyAPI

logger = logging.getLogger(__name__)

def sync_deputy_areas(push_deputy=True, dry_run=False):
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
        for area in Area.objects.filter(source='deputy')
    }

    deputy_areas = {
        area.source_row_id: area
        for area in api.query_all_areas()
    }

    db_areas_set = set((
        srid for srid, area in db_areas.items()
    ))
    dpt_areas_set = set(deputy_areas.keys())

    matches_set = db_areas_set & dpt_areas_set
    del_dpt_set = db_areas_set - dpt_areas_set
    new_dpt_set = dpt_areas_set - db_areas_set
    logger.debug('matches=%s del=%s new=%s' % (matches_set, del_dpt_set, new_dpt_set))
    changelogs = []
    to_update_deputy = []

    # try match by area name (lowercase)
    db_areas_by_name = {
        str(area.name).lower(): area
        for area in Area.objects.filter(
            ~Q(pk__in = [ db_areas[srid].pk for srid in matches_set ])
        )
    }

    with transaction.atomic():
        # update matched rows
        for srid in matches_set:
            db_row = db_areas[srid]
            dpt_row = deputy_areas[srid]
            if db_row.updated > dpt_row.updated:
                # local DB row is newer: push local changes to Deputy
                if (chglog := db_row.mark_update_pushed(dpt_row)):
                    changelogs.append(chglog)
                    if push_deputy:
                        to_update_deputy.append(db_row)
            else:
                if (chglog := db_row.update_from_instance(dpt_row)):
                    changelogs.append(chglog)
                if not dry_run:
                    db_row.save()

        # propagate deletions from deputy to local DB
        for srid in del_dpt_set:
            db_row = db_areas[srid]
            if (chglog := db_row.mark_source_deleted()):
                changelogs.append(chglog)
                if not dry_run:
                    db_row.save()
        
        # propagate added rows from deputy to local DB
        for srid in new_dpt_set:
            new_row = deputy_areas[srid]
            if (chglog := new_row.mark_source_added()):
                changelogs.append(chglog)
                if not dry_run:
                    new_row.save()
            
        if not dry_run:
            ChangeLog.objects.bulk_create(changelogs)

    # now add new rows to Deputy and update changed rows
    if push_deputy and to_update_deputy:
        logger.debug('Updating areas in deputy: ' + ', '.join((
            '[%s %d] %s' % (area.source_row_id, area.pk, area.name) for area in to_update_deputy)))
        logger.info('Pushing %d area updates to Deputy' % len(to_update_deputy))
        api.update_areas(to_update_deputy)
    else:
        logger.info('No areas to update in Deputy')

    status_msg = "%d matches, %d removed in Deputy, %d updated/pushed, %d new rows, %d change logs" % (
        len(matches_set), len(del_dpt_set), len(to_update_deputy), len(new_dpt_set)
    )
    logger.info('%ssync_deputy_areas: %s' % (
        'DRY RUN: ' if dry_run else '', status_msg,
    ))
    return status_msg

def person_name_key(person):
    fname = (person.first_name or '').lower().split()
    lname = (person.last_name or '').lower().split()

    return "_".join(fname[:1] + lname[-1:])

@transaction.atomic
def sync_deputy_people(dry_run=False, no_add=True, match_only=False, company_id=None):
    """
    Match Employee objects from Deputy with Person rows & update Person objects where relevant.
    Try to match everything by name. Warn but ignore rows which aren't found - so they can be
    updated and matched in successive sync attempts.
    """
    api = DeputyAPI()
    if company_id:
        api.default_company_id = company_id

    db_people_by_name = {}
    db_people_by_srid = {}
    num_added = num_unchanged = num_updated = 0
    
    for pers in Person.objects.all():
        if pers.source_row_id:
            db_people_by_srid[pers.source_row_id] = pers
        else:
            name_key = person_name_key(pers)
            if name_key in db_people_by_name:
                logger.warning("Person '%s' (key=%s) may be duplicated, please check & fix" % (
                    pers.name, name_key
                ))
            db_people_by_name[name_key] = pers
    
    changelogs = []

    for emp in api.query_all_employees():
        name_key = person_name_key(emp)
        if emp.source_row_id in db_people_by_srid:
            # already have matching row using Deputy Employee ID
            found_pers = db_people_by_srid.pop(emp.source_row_id)
            if found_pers.source_row_state != 'none':
                found_pers.source_row_state = 'live'
        elif name_key in db_people_by_name:
            found_pers = db_people_by_name.pop(name_key)
            found_pers.source_row_id = emp.source_row_id
            found_pers.source_row_state = 'live'
        else:
            # new Person object
            found_pers = None

            if not emp.active:
                # skip unknown and inactive/archived Deputy employees
                continue
            num_added += 1

            if match_only or no_add:
                logger.warning("Deputy Employee '%s' srid=%s not found in local DB" % (
                    emp.name, emp.source_row_id,
                ))
            else:
                logger.info('Added new person "%s" from Deputy (srid=%s)' % (
                    emp.name, emp.source_row_id,
                ))
                if (chglog := emp.mark_source_added()):
                    changelogs.append(chglog)
                if not dry_run:
                    emp.save()

        if found_pers is not None:
            if not match_only and (chglog := found_pers.update_from_instance(emp)):
                changelogs.append(chglog)
                num_updated += 1

            if not dry_run:
                found_pers.save()

    for pers in db_people_by_srid.values():
        # deactivate deleted employees automatically
        pers.update_field('active', False, source='deputy')
        if (chglog := pers.mark_source_deleted()):
            changelogs.append(chglog)
        if not dry_run:
            pers.save()

    for pers in db_people_by_name.values():
        chg = False
        if pers.active:
            # non-deputy employees are automatically inactivated
            pers.update_field('active', False, source='deputy')
            chg = True
        if (chglog := pers.mark_source_deleted()):
            changelogs.append(chglog)
            chg = True
        if chg and not dry_run:
            pers.save()

    if not dry_run:
        ChangeLog.objects.bulk_create(changelogs)
    
    status_msg = "%d new in Deputy, %d unchanged, %d updated, %d deleted in Deputy, %d not in Deputy, %d change logs" % (
        num_added, num_unchanged, num_updated, len(db_people_by_srid),
        len(db_people_by_name), len(changelogs)
    )
    logger.info(
        '%ssync_deputy_people: %s' % ('DRY RUN: ' if dry_run else '', status_msg)
    )
    return status_msg

    