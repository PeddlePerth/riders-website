const { useState, useMemo, useRef } = require("react");
const { Badge, ButtonGroup, Button, Spinner, Row, Col, Table, Alert } = require("react-bootstrap");
const { CalendarNav, getDateRange } = require("./CalendarNav");
const { useAjaxData, useForceUpdate, useEditableAjaxData } = require("./hooks");
const { firstDayOfWeek, format_time_12h, format_iso_date, get_weekday, format_date } = require("./utils");

function getSummaryBadges(summaryData) {
    if (!summaryData) return;
    const badges = {}; // dict of ISO date: [<Badge/>, ...]

    for (var [date, rosterday] of Object.entries(summaryData.rosterDays)) {
        let isodate = format_iso_date(date);

        let availability = summaryData.riderAvailability[date];
        let riders_available = availability ? Object.keys(availability).length : 0;
        let riders_needed = rosterday.numTourSlots ?? 0;
        let riders_rostered = rosterday.numRiders ?? 0;

        badges[isodate] = [
            riders_available > 0 ? <Badge key={0} pill bg="info">{riders_available}</Badge> : null,
            riders_rostered > 0 ? <Badge key={1} pill bg="success">{riders_rostered}</Badge> : null,
            (riders_needed > 0 && riders_needed > riders_rostered) ? <Badge key={2} pill bg="danger">{riders_needed - riders_rostered}</Badge> : null,
        ];
    }
    return badges;
}

// Roster Editor page: select weeks on the calendar, display roster & save
// set window onbeforeunload with useEffect for checking if saved is false
const monthsAhead = 1, monthsBehind = 1;
function RosterDashboard({ initialDate }) {
    // data for 3 month calendar view + badges
    const [summaryData, loading, summaryDataError, {today}, reloadSummaryData] = useAjaxData(
        window.jsvars.data_url,
        (data, {today}) => {
            let [first, last] = getDateRange(today, 1, 1);
            return {
                summary: true,
                startDate: first.valueOf(),
                endDate: last.valueOf(),
            };
        },
        null,
        () => ({today: new Date(initialDate)})
    );

    const badges = useMemo(() => getSummaryBadges(summaryData), [summaryData]);
    const { rosterDays, riderAvailability, allRiders, bikeTypes } = summaryData || {};

    


    //console.log('sortedSlots', sortedSlots, 'riders unaccounted', ridersUnaccounted);

    return <>
    <Row className="g-3 mb-3 justify-content-start align-items-center" xs="auto">
        <Col key={0} className="fs-1 me-3">Roster Dashboard</Col>
        <Col key={1} className="me-3">
            <Badge key={0} pill className="me-2" bg="info">Num Riders Available</Badge>
            <Badge key={1} pill className="me-2" bg="success">Num Riders on Roster</Badge>
            <Badge key={2} pill className="me-2" bg="danger">Num Riders Needed</Badge>
        </Col>
    </Row>
    <CalendarNav
        today={today}
        badges={badges}
        selectedDay={selectedDay}
        onSelectDay={(date) => {
            reload({selectedDay: date});
        }}
        monthsBehind={monthsBehind}
        monthsAhead={monthsAhead}
    />
    { loading ? <Spinner animation="border"/> : 
    <Row className="mt-3">
        <Col key={0} xs={2} >
            <div className="position-sticky" style={{top: '20px'}}>
                <div className="fs-5 fw-bold">Available Riders</div>
                { riderAvailability && riderAvailability[selectedDay.valueOf()] ? 
                    Object.entries(riderAvailability[selectedDay.valueOf()]).map(
                    ([riderId, ravl]) =>
                        <AvailableRider key={riderId}
                            rider={allRiders[riderId]}
                            notes={ravl.notes}
                            choices={ravl.choices}
                            active
                        />
                ) : <Badge className="fs-6" bg="warning">No riders available today</Badge> }
            </div>
        </Col>
        <Col key={1} xs={7} className="ps-1 pe-1">
            { rosterDataError || !rosterData ?
            <Alert variant="danger">{rosterDataError}</Alert>
             : <RosterTable
                allRiders={allRiders}
                riderAvailability={riderAvailability}
                rosterData={rosterData}
                bikeTypes={bikeTypes}
                onChange={() => onEdit()}
            /> }
        </Col>
    </Row> }
    </>
}

module.exports = {RosterDashboard};