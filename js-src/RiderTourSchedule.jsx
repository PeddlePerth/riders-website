const { useEffect, useRef, forwardRef, useState } = require("react");
const { Spinner, Badge, Alert, Row, Col, Pagination } = require("react-bootstrap");
const { TSBikesInfo } = require("./BikesWidget");
const { useAjaxData } = require("./hooks");
const { WeekNavigator } = require("./TourScheduleViewer");
const { get_venues_summary } = require("./TourVenuesEditor");
const { format_timedelta, format_time_12h, htmlLines, format_iso_date,
     format_short_date, format_time, today, addDays, firstDayOfWeek } = require("./utils");

function getToursWithBreaks(tours) {
    if (!tours) return null;
    let res = [];
    let now = (new Date()).valueOf();
    
    var prev = null;
    for (var i = 0; i < tours.length; i++) {
        if (prev && tours[i].tour.time_start > prev.tour.time_start) {
            res.push({
                now: now >= prev.tour.time_end && now <= tours[i].tour.time_start,
                past: now >= tours[i].tour.time_start,
                isBreak: true,
                timeStart: prev.tour.time_end,
                timeEnd: tours[i].tour.time_start,
            });
        }
        tours[i].now = now >= tours[i].tour.time_start && now <= tours[i].tour.time_end;
        tours[i].past = now >= tours[i].tour.time_end;
        res.push(tours[i]);
        prev = tours[i];
    }
    return res;
}

const RiderTSBreak = forwardRef(({ data }, ref) => {
    let duration = (data.timeEnd - data.timeStart);
    return <div ref={ref} className={
            (data.past ? "bg-opacity-50 bg-secondary " : "") +
            (data.now ? 'text-highlight ' : 'bg-secondary bg-opacity-25 ') + "p-1 py-2 border-bottom"}
        >
        <span className="fw-bold fs-5">
            {format_time_12h(data.timeStart)} - {format_time_12h(data.timeEnd)} &mdash; {format_timedelta(duration)} break
        </span>
    </div>;
});

const RiderTSTour = forwardRef(({ past, now, tourRider, tour, session, allVenues, allRiders, bikeTypes, tourAreas }, ref) => {
    let duration = (tour.time_end - tour.time_start);
    var venuesText = null;
    if (tour.show_venues && tour.venues && tour.venues.length > 0) {
        venuesText = get_venues_summary(tour, allVenues).join('\n');
    }
    const ridersNotMe = tour.riders.filter(tr => tr.rider_id != tourRider.rider_id);
    const area = tourAreas ? tourAreas[tour.area_id] : null;

    return <div className={
            (now ? 'text-highlight ' : '') + 
            (past ? 'bg-secondary bg-opacity-50 ' : '') + "p-1 border-bottom pb-3"} ref={ref}>
        <Row xs={1} md={2}>
            <Col className="lh-lg" xs="auto">
                <div className="ms-2 d-inline-block fw-bold fs-5">
                    <span className="badge" style={{ backgroundColor: area ? area.colour : null }}>
                        { area ? area.display_name : null }
                    </span>&nbsp;
                    {session.title}
                </div>
                { tourRider.rider_role ? <Badge bg="primary" className="ms-2">{tourRider.rider_role}</Badge> : null }
                <div key={1} className="d-inline-block">
                    <span className="ms-2 d-inline-block text-decoration-underline fs-5">{tour.customer_name}</span>&nbsp;
                    <a className="ms-2 d-inline-block" href={`tel:${tour.customer_contact}`}>{tour.customer_contact}</a>
                </div>
                <div key={2} className="d-inline-block">
                    <TSBikesInfo tour={tour} bikeTypes={bikeTypes} className="ms-2 d-inline-block" />
                    { ridersNotMe.length > 0 ? <b>Riding with: </b> : null }
                    { ridersNotMe.map((tr, i) => {
                        let rider = allRiders[tr.rider_id];
                        let role = tr.rider_role_short ? (' (' + tr.rider_role_short + ')') : null;
                        return <div key={i} className="d-inline-block fw-bold">
                            <span className={role ? 'text-decoration-underline' : null}>
                                {rider}{role}{ i < ridersNotMe.length - 1 ? ',' : null}
                            </span>
                            &nbsp;
                        </div>;
                    })}
                </div>
                <div className="ms-2" key={3}><b>Qty:</b> {htmlLines(tour.quantity)}</div>
                <div className="ms-2"><b>Pickup at:</b> {htmlLines(tour.pickup_location)}</div>
            </Col>
            { (tour.notes && tour.notes.trim()) || venuesText ? 
            <Col className="" xs={12} md={6}>
                <div className="p-1 bg-info bg-opacity-10 rounded">
                    { venuesText ? htmlLines(venuesText + '\n\n' + tour.notes) : htmlLines(tour.notes) }
                </div>
            </Col> : null }
        </Row>
    </div>;
});

function inDateRange(date, startDate, endDate) {
    return startDate !== undefined && endDate !== undefined &&
        date.valueOf() >= startDate.valueOf() && 
        date.valueOf() < endDate.valueOf();
}

function getDateRange(toursDate, startDate, endDate) {
    // check if the toursDate is outside date range or if date range not specified
    if (!inDateRange(toursDate, startDate, endDate)) {
        // then create a new date range around the toursDate
        startDate = new Date(toursDate);
        endDate = new Date(toursDate);
        firstDayOfWeek(startDate);
        addDays(endDate, 7);
        firstDayOfWeek(endDate);
    }

    return {
        startDate, endDate, toursDate,
    };
}

const RiderShiftNavigator = ({startDate, endDate, selectedDate, toursByDate, onChangeDate}) => {
    let prevDate = new Date(startDate), nextDate = new Date(endDate);
    addDays(prevDate, -1);
    //addDays(nextDate, 1);
    let allDays = [];
    let curDate = new Date(startDate);
    while (curDate.valueOf() < endDate.valueOf()) {
        allDays.push(curDate);
        curDate = new Date(curDate);
        addDays(curDate, 1);
        //console.log(curDate, curDate.valueOf());
    }

    function getdesc(date) {
        if (toursByDate == null) return 'No tours';
        tours = toursByDate[date.valueOf()];

        if (tours === undefined || tours.length === 0) return 'No tours';
        return <b>{(tours.length == 1 ? '1 tour' : (tours.length + ' tours'))}</b>;
    }

    return <Pagination className="m-1 overflow-auto">
            <Pagination.First onClick={() => onChangeDate(prevDate)}>
                {format_short_date(prevDate)}<br/>&laquo;
            </Pagination.First>
            { allDays.map(date => <Pagination.Item
                    key={date}
                    onClick={() => onChangeDate(date)}
                    active={selectedDate.valueOf() == date.valueOf()}>
                        {format_short_date(date)}
                        <br/>
                        { getdesc(date) }
                    </Pagination.Item>) }
            <Pagination.Last onClick={() => onChangeDate(nextDate)}>
                {format_short_date(nextDate)}<br/>&raquo;
            </Pagination.Last>
        </Pagination>;
};

const RiderTourSchedule = ({ initialDate }) => {
    const currentTourEl = useRef(null);

    const [toursDate, _setToursDate] = useState(initialDate);

    const [data, isLoading, dataError, {startDate, endDate}, reloadData] = 
    useAjaxData(window.jsvars.data_url, 
        (data, {startDate, endDate}) => {
            return { // return actual request data
                startDate: startDate.valueOf(),
                endDate: endDate.valueOf(),
            }
        }, null, () => getDateRange(toursDate));

    function setToursDate(date) {
        if (date.valueOf() === toursDate.valueOf()) return;
        if (date.valueOf() === today().valueOf()) {
            window.history.replaceState(null, '', window.jsvars.today_url);
        } else {
            const toursUrl = window.jsvars.my_url.replace('DATE', format_iso_date(date));
            window.history.replaceState(null, '', toursUrl);
        }

        if (!inDateRange(date, startDate, endDate)) {
            reloadData(getDateRange(date));
        }
        _setToursDate(date);
    }

    var todayDate = toursDate.valueOf();
    var hasTours = data && Object.keys(data.tour_dates).length > 0 &&
        todayDate in data.tour_dates && data.tour_dates[todayDate].length > 0;

    var content = null, hasCurrentTour = false;
    if (isLoading) {
        content = <div className="p-5 text-center"><Spinner animation="border" role="status"></Spinner></div>;
    } else if (hasTours) {
        let todayTours = data.tour_dates[todayDate];

        let toursAndBreaks = getToursWithBreaks(todayTours);
        content = <div className="border">
            { toursAndBreaks.map((tour, i) =>  {
                if (tour.now) hasCurrentTour = true;
                return tour.isBreak ? <RiderTSBreak key={i} data={tour} ref={tour.now ? currentTourEl : null}/> : 
                <RiderTSTour key={i} {...tour} 
                    bikeTypes={data.bikeTypes} allVenues={data.venues} allRiders={data.riders}
                    tourAreas={data.tourAreas}
                ref={tour.now ? currentTourEl : null} />
            }
            )}
        </div>
    } else if (dataError) {
        content = <Alert variant="danger">{dataError}</Alert>;
    } else {
        content = <Alert variant="primary">No tours for today.</Alert>;
    }

    useEffect(() => {
        if (hasCurrentTour && currentTourEl.current) currentTourEl.current.scrollIntoView(); 
    });

    useEffect(() => {
        function onVisChange() {
            if (document.visibilityState == 'visible' && hasCurrentTour && currentTourEl.current) {
                currentTourEl.current.scrollIntoView();
            }
        }
        document.addEventListener('visibilitychange', onVisChange);
        return () => document.removeEventListener('visibilitychange', onVisChange);
    });
    return <div>
        <h2>My tours for { format_short_date(toursDate) }</h2>
        <RiderShiftNavigator 
            startDate={startDate}
            endDate={endDate}
            selectedDate={toursDate}
            toursByDate={data ? data.tour_dates : null}
            onChangeDate={setToursDate}
            />
        {content}
    </div>;
};

module.exports = {RiderTourSchedule};