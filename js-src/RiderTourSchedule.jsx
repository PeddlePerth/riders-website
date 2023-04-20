const { useEffect, useRef, forwardRef } = require("react");
const { Spinner, Badge, Alert, Row, Col } = require("react-bootstrap");
const { TSBikesInfo } = require("./BikesWidget");
const { useAjaxData } = require("./hooks");
const { WeekNavigator } = require("./TourScheduleViewer");
const { get_venues_summary } = require("./TourVenuesEditor");
const { format_timedelta, format_time_12h, htmlLines, format_iso_date, format_short_date, format_time, today } = require("./utils");

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

const RiderTSTour = forwardRef(({ past, now, tourRider, tour, session, allVenues, allRiders, bikeTypes }, ref) => {
    let duration = (tour.time_end - tour.time_start);
    var venuesText = null;
    if (tour.show_venues && tour.venues && tour.venues.length > 0) {
        venuesText = get_venues_summary(tour, allVenues).join('\n');
    }
    const ridersNotMe = tour.riders.filter(tr => tr.rider_id != tourRider.rider_id);

    return <div className={
            (now ? 'text-highlight ' : '') + 
            (past ? 'bg-secondary bg-opacity-50 ' : '') + "p-1 border-bottom pb-3"} ref={ref}>
        <Row xs={1} md={2}>
            <Col className="lh-lg" xs="auto">
                <div className="d-inline-block fw-bold fs-5">{session.title}</div>
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
                <div className="ms-2"><b>Qty:</b> {htmlLines(tour.quantity)}</div>
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

const RiderTourSchedule = ({ initialDate }) => {
    const currentTourEl = useRef(null);

    const [data, isLoading, dataError, {toursDate}, reloadData] = 
    useAjaxData(window.jsvars.data_url, 
        (data, {toursDate}) => {
            if (toursDate.valueOf() === today().valueOf()) {
                window.history.replaceState(null, '', window.jsvars.today_url);
            } else {
                const toursUrl = window.jsvars.my_url.replace('DATE', format_iso_date(toursDate));
    -               window.history.replaceState(null, '', toursUrl);
            }
            return {
                riderTours: true,
                tours_date: toursDate.valueOf()
            }
        }, null, () => ({ toursDate: new Date(initialDate) }));

    var hasTours = data && data.tours.length > 0;

    var content = null, hasCurrentTour = false;
    if (isLoading) {
        content = <div className="p-5 text-center"><Spinner animation="border" role="status"></Spinner></div>;
    } else if (hasTours) {
        let toursAndBreaks = getToursWithBreaks(data.tours);
        content = <div className="border">
            { toursAndBreaks.map((tour, i) =>  {
                if (tour.now) hasCurrentTour = true;
                return tour.isBreak ? <RiderTSBreak key={i} data={tour} ref={tour.now ? currentTourEl : null}/> : 
                <RiderTSTour key={i} {...tour} bikeTypes={data.bikeTypes} allVenues={data.venues} allRiders={data.riders}
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
        <h1>My tours for { format_short_date(toursDate) }</h1>
        <WeekNavigator date={toursDate} onChangeDate={(date) => reloadData({toursDate: date})} />
        {content}
    </div>;
};

module.exports = {RiderTourSchedule};