const { useMemo } = require("react");
const { Badge, Row, Spinner, Alert, Pagination } = require("react-bootstrap");
const { useAjaxData } = require("./hooks");
const { get_weekday, format_date, format_time_12h, firstDayOfWeek, addDays, format_short_date, getWeekName } = require("./utils");

const roleButtons = [
    {id: 'tl', title: 'TL', variant: 'outline-primary'},
    {id: 'noob', title: 'NOOB', variant: 'outline-warning'},
    {id: 'delete', title: 'X', variant: 'outline-danger'},
];

function getOrderedRosterSlots(rosterDay, rosterRiders, allRiders) {
    if (!rosterDay || !allRiders) return [];

    // index roster slots by start and end time, and by tours/hustle
    let slotsIndex = {};
    for (var slot of rosterDay.slots) {
        let key = `${slot.timeStart}_${slot.timeEnd}${slot.tourIds ? 't' : ''}`;
        if (key in slotsIndex) {
            slotsIndex[key].push(slot); // same times, doesn't matter what rider gets it
        } else { 
            slotsIndex[key] = [slot];
            slotsIndex[key].nextSlot = 0; // add an attribute to count the matching of riders to slots
        }
    }

    // 1. Flatten rosterRider swaps in memory so that the initial RosterRider.swaps = [swap1, swap2, ...]
    // invert swap_from_id to a dict of swap_to_ids, for all the RosterRiders which are swaps
    let rr_swap_to = {};
    for (var [rr_id, rr] of Object.entries(rosterRiders)) {
        if (rr.swap_from_id != null)
            rr_swap_to[rr.swap_from_id] = rr_id;
    }

    // Produce a dict of all "starting-at-WH" RosterRider IDs to list of all RosterRiders in swap order
    let ridersUnaccounted = [];
    let allSlots = [];
    for (var rr_root of Object.keys(rr_swap_to).filter(rr_id => rosterRiders[rr_id].swap_from_id == null)) {
        // found root node: traverse swap tree from root to leaves (since it is actually list) and create flat list of swaps
        let swaps = [rr_root];
        let rr_swap = rr_root;
        while (rr_swap != null) {
            rr_swap = rr_swap_to[rr_swap];
            swaps.push(rosterRiders[rr_swap]);
        }

        let rr = rosterRiders[rr_root];
        // find matching slot by key
        let key = `${rr.time_start}_${rr.time_end}${rr.is_tours ? 't' : ''}`;
        if (key in slotsIndex && slotsIndex[key].nextSlot < slotsIndex[key].length) {
            let slots = slotsIndex[key];
            let slot = slots[slots.nextSlot++];
            slot.riders = swaps;
            allSlots.push(slot);
        } else {
            ridersUnaccounted.push(swaps);
        }
    }

    // add any slots which have no riders
    for (var slots of Object.values(slotsIndex)) {
        for (var i = slots.nextSlot; i < slots.length; i++) {
            allSlots.push(slots[i]);
        }
    }

    // Order rosterRiders by start time (first) then number of swaps then rider display name
    let sortedSlots = allSlots.sort((a, b) => {
        if (a.timeStart < b.timeStart) return -1;
        else if (a.timeStart == b.timeStart && a.riders) {
            if (!b.riders) return -1;
            if (a.riders.length < b.riders.length) return -1; // number of swaps
            if (a.riders.length == b.riders.length) { // then first rider's display name
                if (allRiders[a.riders[0].rider_id].display_name < allRiders[b.riders[0].rider_id].display_name) return -1; 
                else return 1;
            } else return 1;
        } else return 1;
    });

    return [sortedSlots, ridersUnaccounted];
}

const RosterSlotTime = ({timeStart, isSwap}) => 
<span className={isSwap ? 'highlight-2' : 'highlight'}>
    [{format_time_12h(timeStart)} {isSwap ? 'SWAP' : '@ WH'}]
</span>;

// Read only roster viewer by day
const RosterDayView = ({ date, rosterDay, allRiders, bikeTypes }) => {
    if (!rosterDay || !allRiders) return null;

    const rosterSlots = useMemo(() => getOrderedRosterSlots(rosterDay, rosterDay.riders, allRiders), [rosterDay]);


    return <div className="border">
        <div key={-1} style={{ backgroundColor: 'lime' }} className="text-align-center">
            <div key={0} className="fw-bold fs-5">{get_weekday(date, true)} {format_date(date)}</div>
            <div key={1}>{rosterDay.notes}</div>
        </div>
        { rosterSlots.map((slot, i) => <div key={i} className="border-top p-1 pb-0">
            { slot.riders ? slot.riders.map((rr, j) => // we have a rider + 0 or more swaps
            <div key={j} className="pb-1">
                <RosterSlotTime timeStart={rr.time_start} isSwap={rr.swap_from_id != null}/> &nbsp;
                { allRiders[rr.rider_id].display_name }
                { rr.role && (rr.role in roleButtons) ? 
                    <Badge key={0} className="ms-1" bg={roleButtons[rr.role].variant}>{roleButtons[rr.role].title}</Badge> : null }
                { rr.bike && (rr.bike in bikeTypes) && rr.bike != 'bike' ?
                    <Badge key={1} className="ms-1" bg='info'>{bikeTypes[rr.bike].name}</Badge> : null }
            </div>) 
                : // OR we have no rider
            <div>
                <RosterSlotTime timeStart={slot.timeStart} isSwap={false}/> &nbsp;
                { slot.bike && (slot.bike in bikeTypes) && slot.bike != 'bike' && false ?
                    <Badge key={1} className="ms-1" bg='info'>{bikeTypes[rr.bike].name}</Badge> : null }
                { slot.tourIds ? 
                    <Badge key={2} className="ms-1" bg="danger">RIDER NEEDED</Badge> :
                    <Badge key={2} className="ms-1" bg="info">[Bike Available]</Badge>
                    }
            </div>}
        </div>)}
    </div>;
};

const WeekNavigator = ({ thisWeek, selectedWeek, changeDate, className }) => {
    function getDate(date, offset) {
        let newDate = new Date(date);
        addDays(newDate, offset);
        return newDate;
    }

    const weeks = [-2, -1, 0, 1, 2].map(w => getDate(thisWeek, 7 * w));
    return <Pagination className={"m-1 overflow-auto" + (className ? ' ' + className : '')}>
        <Pagination.First onClick={() => changeDate(getDate(selectedWeek, -7))} />
        { weeks.map((weekStart, i) => 
        <Pagination.Item
            key={i}
            active={weekStart.valueOf() == selectedWeek.valueOf()}
            onClick={() => changeDate(weekStart)}>
            {getWeekName(thisWeek, weekStart)}
        </Pagination.Item>)}
        <Pagination.Last onClick={() => changeDate(getDate(selectedWeek, 7))} />
    </Pagination>;
}

const RosterViewer = ({ initialDate }) => {
    const thisWeek = new Date(initialDate);
    firstDayOfWeek(thisWeek);

    const [summaryData, isLoading, summaryDataError, {selectedWeek}, reload] = useAjaxData(
        window.jsvars.data_url,
        (data, {selectedWeek}) => {
            let weekEnd = new Date(selectedWeek);
            addDays(weekEnd, 6);
            return {
                startDate: selectedWeek.valueOf(),
                endDate: weekEnd.valueOf(),
            };
        },
        null,
        () => ({
            selectedWeek: thisWeek,
        })
    );

    let hasRosters = summaryData && Object.values(summaryData.rosterDays).some(rday => rday.roster_id !== undefined);

    var content = null;
    if (isLoading) {
        content = <div className="p-5 text-center"><Spinner animation="border" role="status"></Spinner></div>;
    } else if (hasRosters) {
        content = <Row className="g-3">
            { Object.entries(summaryData.rosterDays).map(([date, rosterDay]) => 
                rosterDay.roster_id === undefined ? null : <RosterDayView
                    date={date}
                    rosterDay={rosterDay}
                    allRiders={summaryData.allRiders}
                    bikeTypes={summaryData.bikeTypes}
                />
            )}
        </Row>;
    } else {
        content = <Alert variant="primary">No rosters for this week</Alert>;
    }
    return <div>
        <div className="d-flex align-items-start">
            <h1 className="me-2">Rosters from { format_short_date(selectedWeek) }</h1>
            <WeekNavigator 
                className="align-self-center"
                thisWeek={thisWeek}
                selectedWeek={selectedWeek}
                changeDate={(date) => reload({selectedWeek: date})}/>
        </div>
        { summaryDataError ? <Alert variant="danger">{summaryDataError}</Alert> : null }
        
        {content}
    </div>;
}

module.exports = {RosterDayView, getOrderedRosterSlots, roleButtons, RosterViewer};