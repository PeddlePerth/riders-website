const { useState, useMemo, useEffect } = require("react");
const { Badge, Col, Row, Button, ButtonGroup } = require("react-bootstrap");
const { CalendarNav, getDateRange } = require("./CalendarNav");
const { CheckButton } = require("./components");
const { post_data, WEEKDAYS, firstDayOfWeek, addDays, format_time_12h, format_iso_date, format_date, plural, format_datetime, format_short_date, format_datetime_short, format_timedelta } = require("./utils");

function areaSort(tourAreas) {
    return ([a_area_id, a], [b_area_id, b]) => (tourAreas[a_area_id].sort_order - tourAreas[b_area_id].sort_order);
}

const AreaInfoBadge = ({ tourArea, infoBg, className, children }) => (
    <div className={"AreaInfoBadge" + (className ? ' ' + className : '')}>
        <Badge key={1} bg="none" style={{ backgroundColor: tourArea.colour }}>
            { tourArea.display_name[0] }
        </Badge>
        <Badge key={2} bg={infoBg}>{children}</Badge>
    </div>
);

function getBadges(summaryData, tourAreas) {
    if (!summaryData) return;
    const badges = {};

    for (var d of summaryData.tours) { // each day in the list
        if (!(d.isodate in badges)) badges[d.isodate] = [];
        let dayBadges = badges[d.isodate];
        for (var [area_id, areaInfo] of Object.entries(d.areas).sort(areaSort(tourAreas))) {
            let area = tourAreas[area_id];
            if (!area) continue;
            if (areaInfo.needs_riders > 0)
                dayBadges.push(<AreaInfoBadge key={area_id + '_1'} tourArea={area} infoBg="danger">
                    {areaInfo.needs_riders}<span className="bi-exclamation-triangle-fill ms-1"/></AreaInfoBadge>);
            if (areaInfo.filled > 0)
                dayBadges.push(<AreaInfoBadge key={area_id + '_2'} tourArea={area} infoBg="success">
                    {areaInfo.filled}<span className="bi-check"/></AreaInfoBadge>);
            if (areaInfo.cancelled > 0)
                dayBadges.push(<AreaInfoBadge key={area_id + '_3'} tourArea={area} infoBg="secondary">
                    {areaInfo.cancelled}<span className="bi-x"/></AreaInfoBadge>)
        }
    }
    return badges;
}

function WeeklyTourSummary({ summaryData, weekStart, tourAreas }) {
    const weekEnd = new Date(weekStart);
    addDays(weekEnd, 7);

    const [showDetails, setShowDetails] = useState(false);
    const groupTours = !showDetails;

    const weekData = useMemo(() => {
        const days = [];
        if (!summaryData) return;
        for (var toursDay of summaryData.tours) {
            if (toursDay.date < weekStart) continue;
            if (toursDay.date >= weekEnd) break;
            let isodate = format_iso_date(toursDay.date);

            for (todaysAreaTours of Object.values(toursDay.areas)) {
                let todaysTours = todaysAreaTours.tours;

                if (groupTours) {
                    // group tours by same start/end time and tour type
                    let groupOrder = [];
                    let tours = {};
                    
                    for (var t of todaysAreaTours.tours) {
                        let key = `${t.tour_type}_${t.time_start}_${t.time_end}`;
                        var grp;
                        if (key in tours) {
                            grp = tours[key];
    
                        } else {
                            grp = {
                                tour_type: t.tour_type,
                                time_start: t.time_start,
                                time_end: t.time_end,
                                num_riders: 0,
                                num_bikes: 0,
                                num: 0,
                                cancelled: 0,
                                quantity: '',
                            }
                            tours[key] = grp;
                            groupOrder.push(key);
                        }
    
                        if (!t.cancelled) {
                            tours[key].num_riders += t.num_riders;
                            tours[key].num_bikes += t.num_bikes;
                            tours[key].quantity += t.quantity + '\n';
                            tours[key].num ++;
                        } else {
                            tours[key].cancelled ++;
                            tours[key].num ++;
                        }
                    }
    
                    todaysTours = groupOrder.map(grpkey => tours[grpkey]);
                }

                // organise data into ordered list of days
                let day = Math.round((toursDay.date - weekStart) / (86400 * 1000));
                if (!(day in days)) {
                    days[day] = { // set default for day record
                        date: toursDay.date,
                        isodate: toursDay.isodate,
                        updated: toursDay.updated,
                        area_tours: {},
                    };
                }

                days[day].area_tours[todaysAreaTours.area_id] = todaysTours;

                todaysTours.editUrl = window.jsvars.edit_url
                    .replace('DATE', isodate)
                    .replace('AREA_ID', todaysAreaTours.area_id);
                todaysTours.viewUrl = window.jsvars.view_url
                    .replace('DATE', isodate)
                    .replace('AREA_ID', todaysAreaTours.area_id);
            }
        }
        //for (var i = 0; i < 7; i++) if (days[i] === undefined) days[i] = null;
        return days;
    }, [summaryData, weekStart.getTime(), groupTours]);

    //console.log(weekData);
    const reportUrl = window.jsvars.report_url.replace('DATE', format_iso_date(weekStart));
    const venuesUrl = window.jsvars.venues_report_url.replace('DATE', format_iso_date(weekStart));
    //const updateUrl = window.jsvars.update_url;

    return <div className="TourSummary">
        <Row className="Header my-2" key={-1}>
            <div>
                <h3>Week from {format_date(weekStart)} to {format_date(weekEnd - 1)}</h3>
                <Button variant="primary" className="mx-2" href={reportUrl}>Weekly Tour Pays</Button>
                <Button variant="primary" className="" href={venuesUrl}>Weekly Venue Bookings</Button>
                <CheckButton variant="primary" className="mx-2" text="Show Details" checked={showDetails} onChange={setShowDetails} />
            </div>
        </Row>
        <Row className="Header" key={0}>
            {weekData ? weekData.map((day, i) => 
                 day == null ? null : <Col key={i}>
                    
                </Col>
                ) : null}
        </Row>
        <Row key={1}>
        {weekData ? weekData.map((day, di) =>
            day == null ? null : // day column: header + list of tours
            <Col className="TourSummaryDay" key={di}>
                <div className="Header mb-1">
                <span className="fs-5 fw-bold me-2">{format_short_date(day.date)}</span>&nbsp;
                <span>Fetched {format_timedelta((new Date().valueOf()) - weekData[di].updated)} ago</span>

                { Object.entries(day.area_tours).map(([area_id, todaysTours]) => (
                    <div className="d-inline-block m-1 p-1 rounded-1" key={area_id} style={{ backgroundColor: tourAreas[area_id].colour }}>
                        <Badge pill bg="light" text="dark" className="d-block mb-1">{ tourAreas[area_id].display_name }</Badge>
                    <ButtonGroup size="sm">
                        <Button variant="light"
                            href={todaysTours.viewUrl} key={1}>View
                            </Button>
                        <Button variant="secondary" href={todaysTours.editUrl} key={2}>
                            Edit
                        </Button>
                    </ButtonGroup>
                    </div>
                )) }
                </div>
                { // tours list per day
                Object.entries(day.area_tours)
                    .sort(areaSort(tourAreas))
                    .map(([area_id, areaTours]) => areaTours.map((tour, ti) => 
                <div className="TourSummaryTour" key={ti}>
                    <div className="fw-bold">
                        { tour.tour_type }&nbsp;{ (groupTours && tour.num > 1) ? ' (x' + tour.num + ')' : null }
                        <Badge pill bg="none" style={{ backgroundColor: tourAreas[area_id].colour }}>{ tourAreas[area_id].display_name }</Badge>
                    </div>
                    <div className="Time">{ format_time_12h(tour.time_start) + '—' + format_time_12h(tour.time_end) }</div>
                    { groupTours ? null : <div className="Qty">{ tour.quantity }</div> }
                    <div className="Info">
                        { tour.cancelled ?
                            <Badge pill bg="secondary" className="mx-1" key={2}>
                                { groupTours && tour.num > 1 ? plural(tour.cancelled, ' cancellation', ' cancellations') : 'CANCELLED' }
                            </Badge> : (
                                tour.num_riders < tour.num_bikes ? 
                                <Badge pill bg="danger" key={1}>{plural(tour.num_bikes - tour.num_riders, ' RIDER', ' RIDERS') + ' NEEDED'}</Badge> :
                                <Badge pill bg="success" key={1}>{plural(tour.num_riders, ' RIDER', ' RIDERS')}</Badge>
                            ) }
                    </div>
                </div> ))
                }
            </Col>) : 'Loading...'}
        </Row>
    </div>;
}

function TourDashboard({ date_today, data_url, last_scan_begin, last_scan, scan_interval, scan_ok, tourAreas }) {
    const [summaryData, setSummaryData] = useState(null);
    const [selected, setSelected] = useState(date_today);
    const badges = useMemo(() => getBadges(summaryData, tourAreas), [summaryData]);
    
    useEffect(() => {
        let dateRange = getDateRange(date_today, 1, 1);
        post_data(data_url, {
            start_date: dateRange[0].getTime(),
            end_date: dateRange[1].getTime(),
        }, (ok, data) => {
            if (ok) setSummaryData(data);
            else console.log('TourDashboard fetch error:', data);
        });
    }, [date_today]);

    const weekStart = new Date(selected);
    firstDayOfWeek(weekStart);

    return <div className="TourDashboard">
        <Row className="align-items-center g-3" xs="auto">
            <Col key={1}><h1>Tour Dashboard</h1></Col>
            <Col key={2}>
                { Object.values(tourAreas)
                    .sort((a, b) => a.sort_order - b.sort_order)
                    .map(({area_id, display_name, colour}) => (
                        <Badge key={area_id} pill style={{backgroundColor: colour}} bg="none" className="d-block mb-1">
                            { display_name }</Badge>
                    ))}
            </Col>
            <Col key={11}>
                <Badge key={1} className="d-block mb-1" pill bg="danger">
                    <span className="bi-exclamation-triangle-fill"/>&nbsp;Tours - Riders Needed</Badge>
                <Badge key={2} className="d-block mb-1" pill bg="success">
                    <span className="bi-check"/>&nbsp;Tours - Riders Filled</Badge>
                <Badge key={3} className="d-block" pill bg="secondary">
                    <span className="bi-x"/>&nbsp;Tours - Cancelled</Badge>
            </Col>
            <Col key={5}>
                <div key={2}>
                    <b>Last automatic scan</b> at {format_datetime(last_scan)} ({format_timedelta((new Date().valueOf()) - last_scan)} ago)
                </div>
                <div key={1}>{ scan_ok ? 'Auto updates OK' : <b>Auto updates not running!</b> } (set to run every { scan_interval } minutes)</div>
            </Col>
        </Row>
        <CalendarNav
            selectedWeek={weekStart} today={ date_today } badges={badges}
            onSelectWeek={setSelected}
            monthsBehind={1} monthsAhead={1}
            />
        <WeeklyTourSummary
            summaryData={summaryData}
            weekStart={weekStart}
            tourAreas={tourAreas}
            />
    </div>;
}

module.exports = TourDashboard;