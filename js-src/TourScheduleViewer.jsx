const { useState, useEffect } = require("react");
const { Row, Col, Badge, Pagination, Alert, Spinner, Dropdown, Stack, ButtonGroup, Button } = require("react-bootstrap");
const { TSBikesInfo, count_bikes, join_bikes, TSRiderInfo } = require("./BikesWidget");
const { CheckButton } = require("./components");
const { useAjaxData } = require("./hooks");
const { get_venues_summary } = require("./TourVenuesEditor");
const { format_short_date, htmlLines, plural, firstDayOfWeek, addDays, post_data, format_iso_date, today } = require("./utils");

function TSHeaderCell({title, size, fontSize, isLast}) {
    return <Col xs={size} className={"p-2" + (isLast ? "" : " border-end")}
        style={{ backgroundColor: 'lime', fontWeight: 'bold', fontSize: fontSize }}>
        {title}
    </Col>;
}

function TSSessionRow({ session, numRiders }) {
    return <div className="p-2" style={{
        backgroundColor: 'lightsalmon',
        textDecorationLine: 'underline',
        fontWeight: 'bold',
        fontSize: '85%',
    }}>
        { session.title } &mdash; {
        plural(numRiders, ' rider', ' riders')}
    </div>;
}

function TSCancelledBadge() {
    return <Badge bg='secondary' className="mx-1">CANCELLED</Badge>;
}

function TSTourRow({ tour, allRiders, allVenues, bikeTypes }) {
    return <Row className="TSTourRow g-0 border-bottom">
        <Col key={1} xs={8}>
            <Row className="g-0 h-100">
                <Col key={1} xs={3} className="p-1 border-end riders text-break"
                    style={{ backgroundColor: 'lightcoral', fontSize: '110%', fontWeight: 'bold' }}>
                    <div className="p-1">
                        <TSBikesInfo tour={tour} bikeTypes={bikeTypes} />

                        { tour.riders.map((tr, i) => {
                            let rider = allRiders[tr.rider_id];
                            if (!rider) {
                                return <div key={i} className="d-inline-block">{ tr.rider_id } - { tr.rider_role_short }</div>;
                            }
                            let role = tr.rider_role_short ? (' (' + tr.rider_role_short + ')') : null;
                            return <div key={i} className="d-inline-block">
                                <span className={role ? 'text-decoration-underline' : null}>
                                    {rider.title}{role}{ i < tour.riders.length - 1 ? ',' : null}
                                </span>
                                &nbsp;
                            </div>;
                        })}

                        { tour.source_row_state == 'deleted' ? <TSCancelledBadge/> : <TSRiderInfo tour={tour}/> }
                    </div>
                </Col>
                <Col key={2} xs={2} className="p-1 border-end text-break" style={{ textDecorationLine: 'underline' }}>
                    { htmlLines(tour.customer_name) }
                </Col>
                <Col key={3} xs={2} className="p-1 border-end text-break">
                    <a href={`tel:${tour.customer_contact}`}>{tour.customer_contact}</a>
                </Col>
                <Col key={4} xs={3} className="p-1 border-end text-break">
                    { htmlLines(tour.quantity, ['(under 13)']) }
                </Col>
                <Col key={5} xs={2} className="p-1 border-end text-break">
                    { htmlLines(tour.pickup_location) }
                </Col>
            </Row>
        </Col>
        <Col key={2} xs={4} className="p-1 text-break">
            { tour.venue_notes ? htmlLines(tour.venue_notes + '\n\n' + tour.notes) : htmlLines(tour.notes) }
        </Col>
    </Row> ;
}

function WeekNavigator({ date, onChangeDate }) {
    // generate days of week from current tour date
    var weekStart = new Date(date);
    firstDayOfWeek(weekStart);
    var prev = new Date(weekStart);
    addDays(prev, -1);
    var next = new Date(weekStart);
    addDays(next, 7);
    var days = [];
    for (var i = 0; i < 7; i++) {
        var day = new Date(weekStart);
        addDays(day, i);
        days[i] = day;
    }

    return <Pagination className="my-1 overflow-auto">
            <Pagination.First onClick={() => onChangeDate(prev)} />
            { days.map(day => <Pagination.Item
                    key={day}
                    onClick={() => onChangeDate(day)}
                    active={day.valueOf() == date.valueOf()}>
                        {format_short_date(day)}
                    </Pagination.Item>) }
            <Pagination.Last onClick={() => onChangeDate(next)} />
        </Pagination>;
}

function TourScheduleTable({ toursDate, sessionOrder, allTours, allSessions, allRiders, allVenues, bikeTypes, filterForRider, showCancelled }) {
    var numTours = 0;
    var sessionRows = sessionOrder.map(sessId => {
        let sessTours = 0;
        let sessRiders = 0;
        let tourRows = allSessions[sessId].tour_ids.map(tourId => {
            let tour = allTours[tourId];
            if (tour.source_row_state == 'deleted') {
                if (!showCancelled) return null;
            } else {
                sessRiders += count_bikes(tour.bikes);
            }

            if (filterForRider != null && !tour.riders.some(tr => tr.rider_id == filterForRider))
                return null;
            numTours ++;
            sessTours ++;
            return <TSTourRow key={tourId} tour={tour} allRiders={allRiders} allVenues={allVenues} bikeTypes={bikeTypes}/>;
        });

        if (sessTours == 0) return null;
        return <div key={sessId} className="TSSession">
            <TSSessionRow session={allSessions[sessId]} numRiders={sessRiders}/>
            { tourRows }
        </div>
    });

    return <div className="position-relative">
        {numTours == 0 ? <Alert variant="primary">You have no tours today.</Alert> : null }
        <div className="TourSchedule">
        <div className="border">
        <Row key={0} className="Header g-0">
            <Col key={1} xs={8}>
                <Row className="g-0">
                    <TSHeaderCell key={1} size={3} fontSize="110%" title={`Riders (${format_short_date(toursDate)})`} />
                    <TSHeaderCell key={2} size={2} title="Customer Name" />
                    <TSHeaderCell key={3} size={2} title="Customer Phone" />
                    <TSHeaderCell key={4} size={3} title="Quantity" />
                    <TSHeaderCell key={5} size={2} title="Pickup at" />
                </Row>
            </Col>
            <TSHeaderCell key={2} size={4} title="Notes" isLast={true}/>
        </Row>
        {sessionRows}
        </div>
    </div>
    </div>;
}

function FetchToursWidget({ toursDate, onComplete }) {
    const [xhr, setXhr] = useState(null);

    return <Dropdown as={ButtonGroup} onSelect={(key, e) => {
            if (xhr && !xhr.status) return;
            setXhr(post_data(window.jsvars.update_url, {
                tours_date: toursDate.valueOf(),
                update_rezdy: !!(key & 1),
                update_fringe: !!(key & 2),
            }, function (ok, data) {
                if (ok) {
                    onComplete(data.msgs_success, data.msgs_error);
                } else {
                    onComplete([], ['Update error: ' + data]);
                }
            }));
        }}>
            <Dropdown.Toggle id="dropdown-fetch-tours">
                Update Tours Data
                { (xhr && !xhr.status) ? <Spinner className="ms-2" as="span" role="status" animation="border" size="sm"/> : null }
            </Dropdown.Toggle>
            <Dropdown.Menu>
                <Dropdown.Item key={1} eventKey={1}>Scan Rezdy Manifest</Dropdown.Item>
                <Dropdown.Item key={2} eventKey={2}>Scan Fringe Bookings</Dropdown.Item>
                <Dropdown.Item key={3} eventKey={3}>Scan All</Dropdown.Item>
            </Dropdown.Menu>
        </Dropdown>;
}

function TourScheduleViewer({ tourAreas, initialAreaId, initialDate, isAdmin, myRiderId }) {
    const [errors, setErrors] = useState([]); // messages & errors from Fetch Tour Data widget
    const [msgs, setMessages] = useState([]);
    const [filterRider, setFilterRider] = useState(false);
    const [showCancelled, setShowCancelled] = useState(false);

    const [data, isLoading, dataError, {toursDate, tourAreaId}, reloadData] = 
        useAjaxData(window.jsvars.data_url, 
            (data, {toursDate, tourAreaId}) => {
                if (toursDate.valueOf() === today().valueOf()) {
                    const todayUrl = window.jsvars.today_url.replace('AREA_ID', tourAreaId);
                    window.history.replaceState(null, '', todayUrl);
                } else {
                    const toursUrl = window.jsvars.view_url
                        .replace('DATE', format_iso_date(toursDate))
                        .replace('AREA_ID', tourAreaId);
    -               window.history.replaceState(null, '', toursUrl);
                }
                $('title').text(tourAreas[tourAreaId].display_name);
                return {
                    tours_date: toursDate.valueOf(),
                    tour_area_id: tourAreaId,
                }
            }, null, () => ({ toursDate: new Date(initialDate), tourAreaId: initialAreaId }));

    // override the nav button behaviour to avoid rebooting the tour schedule viewer
    useEffect(() => {
        function onAreaNavClick(e) {
            e.preventDefault();
            reloadData({
                toursDate: toursDate.valueOf(),
                tourAreaId: parseInt(e.target.attributes['data-area-id'].value)
            });
        }
        $('.tour-schedule-area').on('click', onAreaNavClick);
        return () => {
            $('.tour-schedule-area').off('click', onAreaNavClick);
        };
    });

    const editUrl = window.jsvars.edit_url
        .replace('DATE', format_iso_date(toursDate))
        .replace('AREA_ID', tourAreaId);
    const weekStart = new Date(toursDate);
    firstDayOfWeek(weekStart);
    const payUrl = window.jsvars.report_url.replace('DATE', format_iso_date(weekStart));
    const venuesUrl = window.jsvars.venues_report_url.replace('DATE', format_iso_date(weekStart));

    var hasTours = data && data.session_order.length > 0;
    var content = null;
    if (isLoading) {
        content = <div className="p-5 text-center"><Spinner animation="border" role="status"></Spinner></div>;
    } else if (hasTours) {
        content = <TourScheduleTable
            toursDate={data.tours_date}
            sessionOrder={data.session_order}
            allTours={data.tours}
            allSessions={data.sessions}
            allRiders={data.riders}
            allVenues={data.venues}
            bikeTypes={data.bike_types}
            filterForRider={filterRider ? myRiderId : null}
            showCancelled={showCancelled}
        />;
    } else {
        content = <Alert variant="primary">No tours for today.</Alert>;
    }

    let allErrors = [
        ...errors
    ];
    if (dataError) {
        allErrors.push(dataError);
    }

    const tourArea = tourAreas[tourAreaId];
    return <div>
        { allErrors.map((error, i) => <Alert key={'e' + i} variant="danger">{error}</Alert>) }
        { msgs.map((msg, i) => <Alert key={'m' + i} variant="success">{msg}</Alert>) }
        <WeekNavigator date={toursDate} onChangeDate={(date) => {
                reloadData({tourAreaId, toursDate: date});
                setErrors([]);
                setMessages([]);
            }}/>
        { isAdmin ? 
        <ButtonGroup className="mb-1 mt-1 me-2 flex-wrap">
            <FetchToursWidget toursDate={toursDate} onComplete={(msgs, errs) => {
                reloadData();
                setErrors(errs); setMessages(msgs); }} />
            <Button variant="secondary"
                style={{ backgroundColor: tourArea.colour }}
                href={editUrl}>Edit Schedule</Button>
            <Button variant="secondary" href={payUrl}>Weekly Tour Pays</Button>
            <Button variant="secondary" href={venuesUrl}>Weekly Venue Bookings</Button>
        </ButtonGroup> : null }
        { myRiderId != null ? <ButtonGroup className="mb-1 mt-1 me-2">
            <CheckButton checked={filterRider} text="Show only my tours" onChange={setFilterRider} />
        </ButtonGroup> : null }
        <ButtonGroup className="mb-1 mt-1 me-2">
            <CheckButton checked={showCancelled} text="Show cancelled tours" onChange={setShowCancelled} />
        </ButtonGroup>
        <h2 className="mt-3 mb-3">
            <span className="p-1 rounded-3 text-white" style={{backgroundColor: tourArea.colour}}>
                { tourArea.display_name }
            </span>&nbsp;
            - { format_short_date(toursDate) }
        </h2>
        {content}
    </div>;
}

module.exports = {
    TourScheduleTable,
    TourScheduleViewer,
    TSCancelledBadge,
    WeekNavigator,
};