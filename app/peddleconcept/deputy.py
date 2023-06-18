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
        len(matches_set), len(del_dpt_set), len(to_update_deputy), len(new_dpt_set), len(changelogs),
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
def sync_deputy_people(dry_run=False, disable_riders=False, no_add=True, match_only=False, company_id=None):
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
        chg = False
        if emp.source_row_id in db_people_by_srid:
            # already have matching row using Deputy Employee ID
            found_pers = db_people_by_srid.pop(emp.source_row_id)
            if found_pers.source_row_state != 'none':
                found_pers.source_row_state = 'live'
                chg = True
        elif name_key in db_people_by_name:
            found_pers = db_people_by_name.pop(name_key)
            found_pers.source_row_id = emp.source_row_id
            found_pers.source_row_state = 'live'
            chg = True
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
            logger.debug('Matched Person with Employee: Local/Deputy: (%s) %s - %s (%s)' %(
                found_pers.pk, found_pers.name, emp.name, emp.source_row_id,
            ))
            if not match_only and (chglog := found_pers.update_from_instance(emp)):
                changelogs.append(chglog)
                num_updated += 1
                chg = True
            else:
                num_unchanged += 1

            if chg and not dry_run:
                found_pers.save()

    num_deleted = 0
    for pers in db_people_by_srid.values():
        # deactivate deleted employees automatically
        chg = pers.update_field('active', False, source='deputy')
        if (chglog := pers.mark_source_deleted()):
            chg = True
            changelogs.append(chglog)
        if chg:
            num_deleted += 1
            if not dry_run:
                pers.save()

    num_disabled = 0
    if disable_riders:
        for pers in db_people_by_name.values():
            chg = False
            if pers.active:
                # non-deputy employees are automatically inactivated
                pers.update_field('active', False, source='deputy')
                chg = True
            if (chglog := pers.mark_source_deleted()):
                changelogs.append(chglog)
                chg = True
            if chg:
                num_disabled += 1
                if not dry_run:
                    pers.save()

    if not dry_run:
        ChangeLog.objects.bulk_create(changelogs)
    
    status_msg = (
        "%d new in Deputy%s, %d unchanged, %d updated, %d deleted "
        "in Deputy, %d not in Deputy%s, %d change logs"
    ) % (
        num_added, ' - added' if not no_add else '', num_unchanged, num_updated, num_deleted,
        num_disabled, ' - disabled' if disable_riders else '', len(changelogs),
    )
    logger.info(
        '%ssync_deputy_people: %s' % ('DRY RUN: ' if dry_run else '', status_msg)
    )
    return status_msg

def sort_rosters(rosters_list):
    return sorted(
        sorted(rosters_list, key=lambda r: (r.person.name if r.person else '')),
        key=lambda r: r.time_start
    )

def sync_deputy_rosters(tours_date, area, tour_rosters_list, dry_run=False):
    """
    Shift swaps? Some rosters in Deputy may be changed remotely - if they match the key then 
        we could update them locally.
        - but this would also have to update the tour riders, in theory, so we don't do that
        - for now, it's enough to just push the updates and overwrite everything in Deputy
    Also nobody is using them!

    Since the tour schedule shifts are not associated in any way with actual Roster instances or Deputy Ids,
        they have to be matched each time based on the start/end times and break slots if we want to 'update' them
        (as opposed to delete all & create new each time).
    
    Some rosters may not upload properly to Deputy, eg. if there are scheduling conflicts. So we keep local
    Roster instances with the requested tour slot data (for the Tour Schedule Editor to review) but with
    null source row IDs indicating lack of corresponding Deputy rosters.

    Returns a list of Roster instances for Deputy (or are in deputy if dry_run=False) + list of changelogs
    """

    people_by_srid = {
        p.source_row_id for p in Person.objects.filter(source_row_state='live')
        if p.source_row_id
    }

    api = DeputyAPI()
    try:
        dpt_rosters = api.query_rosters(tours_date, tours_date, area, people_by_srid=people_by_srid)
    except Exception as e:
        logger.error('Deputy query_rosters error: %s: %s' % (type(e).__name__, str(e)))
        return [], []
    
    # Live Rosters in Deputy
    dpt_rosters_by_key = {} # match with tour schedule shifts
    dpt_rosters_manual = [] # rosters not created automatically in Deputy will not be affected by the sync
    for roster in dpt_rosters:
        key = roster.cmp_key()
        if dpt_rosters_by_key._is_manual:
            dpt_rosters_manual.append(roster)
            continue

        dpt_rosters_by_key[roster.cmp_key()] = roster
        
        if roster.person_id and roster.person_id in key_rosters:
            logger.warning("Got duplicated deputy roster for person %s on date %s" % (
                roster.person.name, roster.time_start.date().isoformat(),
            ))
        elif roster.person_id is None:
            if roster.employee_id:
                logger.warning("Missing local record for Person with Deputy Employee Id %s" % roster.employee_id)
        
    # Rosters calculated from tour schedule (source of truth for all roster data)
    tour_rosters_by_key = {
        roster.cmp_key(): roster
        for roster in tour_rosters_list
    }
    
    # match the Deputy Rosters with Tour schedule ones by key
    dpt_rosters_set = set(dpt_rosters_by_key.keys())
    tour_rosters_set = set(tour_rosters_by_key.keys())

    rosters_matching = dpt_rosters_set & tour_rosters_set # update these if they have changed somehow
    dpt_rosters_extra = dpt_rosters_set - rosters_matching # delete extraneous rosters in Deputy
    tour_rosters_extra = tour_rosters_set - rosters_matching # add missing rosters to Deputy

    logger.info('Match and compare Tour Rosters with Deputy: %d to add, %d matching, %d to delete' % (
        len(tour_rosters_extra), len(rosters_matching), len(dpt_rosters_extra),
    ))

    results = [] # keep track of all the rosters we either tried to add, remove or delete
    results_errors = [] # and any rosters where add/update/delete failed

    # create changelogs for the deputy rosters - pretend they are in the DB for the sake of generating changes
    changelogs = []

    num_add_ok = num_add_fail = 0
    num_unchanged = num_update_ok = num_update_fail = 0
    num_delete_ok = num_delete_fail = 0
    logger.info('%sUpdating rosters in Deputy for date %s, area %s' % (
        'DRY RUN: ' if dry_run else '', tours_date.isoformat(), area.name,
    ))
    # Add rosters to Deputy & record changelogs for successful items
    rosters_added = [ tour_rosters_by_key[key] for key in tour_rosters_extra ]
    if not dry_run:
        try:
            rosters_added = api.add_rosters(rosters_added)
        except Exception as e:
            logger.error('add_rosters error %s: %s'  % (type(e).__name__, str(e)))
    
    for r in rosters_added:
        key = r.cmp_key()
        if r.source_row_id or dry_run:
            num_add_ok += 1
            if (chglog := tour_rosters_by_key[key].mark_source_added()):
                changelogs.append(chglog)
            results.append(r)
        else:
            r.source_row_state = 'add_error'
            logger.debug('add_rosters failed for Roster: %s' % key)
            num_add_fail += 1
            results_errors.append(r)
    
    # Update rosters with changes & record changelogs
    rosters_to_update = {}
    for key in rosters_matching:
        # update the tour roster from the deputy one so the full tour slots are retained
        roster = tour_rosters_by_key[key]
        dpt_roster = dpt_rosters_by_key[key]
        roster.source_row_id = dpt_roster.source_row_id # make sure Deputy ID is preserved

        if (chglog := roster.update_from_instance(dpt_roster)):
            roster.source_row_state = 'changed' 
            changelogs.append(chglog)
            rosters_to_update[roster.source_row_id] = roster
        else:
            roster.source_row_state = 'unchanged' # record change status with source_row_state for the Roster viewer
            num_unchanged += 1
            results.append(r)
    
    if not dry_run and rosters_to_update:
        try:
            updated_ids, update_error_ids = api.update_rosters(rosters_to_update)
        except Exception as e:
            logger.error('update_rosters error %s: %s' % (type(e).__name__, str(e)))
            updated_ids = []
            update_error_ids = rosters_to_update.keys()

        for srid in updated_ids:
            r = rosters_to_update[srid] 
            results.append(rosters_to_update[srid])
        for srid in update_error_ids:
            r = rosters_to_update[srid]
            logger.debug('update_rosters failed for Deputy Roster with ID: %s' % srid)
            r.source_row_state = 'update_error'
            results_errors.append(r)

        num_update_ok = len(updated_ids)
        num_update_fail = len(update_error_ids)
    else:
        num_update_ok = len(rosters_to_update)
        num_update_fail = 0
        for roster in rosters_to_update.values():
            results.append(roster)
    
    rosters_to_delete = {
        dpt_rosters_by_key[key].source_row_id: dpt_rosters_by_key[key]
        for key in dpt_rosters_extra
    }
    if not dry_run and rosters_to_delete:
        try:
            deleted_ids = api.delete_rosters(rosters_to_delete.keys())
        except Exception as e:
            deleted_ids = []
            logger.error('delete_rosters error %s: %s' % (type(e).__name__, str(e)))
    else:
        deleted_ids = rosters_to_delete.keys()

    # delete non-matching rosters
    for srid, roster in rosters_to_delete.items():
        if srid in deleted_ids:
            if (chglog := roster.mark_source_deleted()):
                changelogs.append(chglog)
            num_delete_ok += 1
            results.append(roster)
        else:
            num_delete_fail += 1
            results_errors.append(roster)

    logger.info('%sSync Deputy rosters: added %d (%d failed), updated %d (%d unchanged, %d failed), deleted %d (%d failed), %d changelogs' % (
        'DRY_RUN: ' if dry_run else '', num_add_ok, num_add_fail, num_update_ok, num_unchanged, num_update_fail, num_delete_ok, num_delete_fail, len(changelogs),
    ))
    if not dry_run:
        ChangeLog.bulk_create(changelogs)

    return sort_rosters(results), sort_rosters(results_errors)


