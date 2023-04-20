const { useState, useMemo, useEffect } = require("react");
const { Badge, Col, Row, Button, ButtonGroup } = require("react-bootstrap");
const { CalendarNav, getDateRange } = require("./CalendarNav");
const { CheckButton } = require("./components");
const { post_data, WEEKDAYS, firstDayOfWeek, addDays, format_time_12h, format_iso_date, format_date, plural, format_datetime, format_short_date, format_datetime_short, format_timedelta } = require("./utils");

function getBadges(summaryData) {
    if (!summaryData) return;
    const badges = {};

    for (var d of summaryData.tours) {
        badges[d.isodate] = [
            ((d.needs_riders > 0) ? <Badge pill bg="danger" key={0}>{d.needs_riders}</Badge> : null),
            ((d.filled > 0) ? <Badge pill bg="success" key={1}>{d.filled}</Badge> : null),
            ((d.cancelled > 0) ? <Badge pill bg="secondary" key={2}>{d.cancelled}</Badge> : null),
        ];
    }
    return badges;
}

function WeeklyTourSummary({ summaryData, weekStart }) {
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
            toursDay.editUrl = window.jsvars.edit_url.replace('DATE', isodate);
            toursDay.viewUrl = window.jsvars.view_url.replace('DATE', isodate);

            var todaysTours = toursDay.tours;
            if (groupTours) {
                // group tours by same start/end time and tour type
                let groupOrder = [];
                let tours = {};
                
                for (var t of toursDay.tours) {
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

            let day = Math.round((toursDay.date - weekStart) / (86400 * 1000));
            days[day] = {
                ...toursDay,
                tours: todaysTours,
            };
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
                    <h5 className="mx-2">{format_short_date(day.date)}</h5>
                    <ButtonGroup size="sm" className="mx-1">
                        <Button variant="primary" href={weekData[i].viewUrl} key={1}>View</Button>
                        <Button variant="secondary" href={weekData[i].editUrl} key={2}>Edit</Button>
                    </ButtonGroup>
                    <div>Fetched {format_timedelta((new Date().valueOf()) - weekData[i].updated)} ago</div>
                </Col>
                ) : null}
        </Row>
        <Row key={1}>
        {weekData ? weekData.map((day, di) =>
            <Col className="TourSummaryDay" key={di}>
                {day == null ? null : day.tours.map((tour, ti) => 
                <div className="TourSummaryTour" key={ti}>
                    <div className="Type">{ tour.tour_type }&nbsp;{ (groupTours && tour.num > 1) ? (
                        <Badge pill bg="info">{tour.num} bookings</Badge>) : null }</div>
                    <div className="Time">{ format_time_12h(tour.time_start) + '—' + format_time_12h(tour.time_end) }</div>
                    { groupTours ? null : <div className="Qty">{ tour.quantity }</div> }
                    <div className="Info">
                        { tour.num_riders < tour.num_bikes ? 
                            <Badge pill bg="danger" key={1}>{plural(tour.num_bikes - tour.num_riders, ' RIDER', ' RIDERS') + ' NEEDED'}</Badge> :
                            <Badge pill bg="success" key={1}>{plural(tour.num_riders, ' RIDER', ' RIDERS')}</Badge> }
                        { tour.cancelled ?
                            <Badge pill bg="secondary" className="mx-1" key={2}>{ groupTours && tour.num > 1 ? plural(tour.cancelled, ' cancellation', ' cancellations') : 'CANCELLED' }</Badge> : null }
                    </div>
                </div>)}
            </Col>) : 'Loading...'}
        </Row>
    </div>;
}

function TourDashboard({ date_today, data_url, last_scan_begin, last_scan, scan_interval, scan_ok }) {
    const [summaryData, setSummaryData] = useState(null);
    const [selected, setSelected] = useState(date_today);
    const badges = useMemo(() => getBadges(summaryData), [summaryData]);
    
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
            <Col key={2}><Badge pill bg="danger">Tours - Riders Needed</Badge></Col>
            <Col key={3}><Badge pill bg="success">Tours - Riders Filled</Badge></Col>
            <Col key={4}><Badge pill bg="secondary">Tours - Cancelled</Badge></Col>
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
        <WeeklyTourSummary summaryData={summaryData} weekStart={weekStart}></WeeklyTourSummary>
    </div>;
}

module.exports = TourDashboard;