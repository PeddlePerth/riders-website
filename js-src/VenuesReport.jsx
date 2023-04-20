const { useRef, useState, useEffect } = require("react");
const { Container, Row, Col, Stack, Button } = require("react-bootstrap");
const { format_date, getMailto, format_time_12h, format_short_date } = require("./utils");

function VenueWithBookings({name, email, contactName, bookings}) {
    return <Col className="VenueWithBookings m-1 p-1">
        <div className="fs-4 fw-bold text-decoration-underline mb-1">{ name }</div>
        <div className="mb-2">
            { contactName ? <div><b>Contact:</b> {contactName}&nbsp;</div> : null }
            <a href={`mailto:${email}`}>{email}</a>
        </div>
        <div className="user-select-all">
        { bookings.map(vdate => (
            <div className="mx-1 mb-4" key={vdate.date}>
                <div className="fs-5 fw-bold">{ format_short_date(vdate.date) }</div>
                { vdate.times.map(timeslot => (
                <div key={timeslot.time_arrive} className="">
                    <div className="time" style={{ fontWeight: 'bold' }}>
                        {format_time_12h(timeslot.time_arrive)} &mdash; {format_time_12h(timeslot.time_depart)}
                    </div>
                    {timeslot.tours.map((tour, i) => (
                        <div key={i} className="ms-2">{tour.quantity}</div>
                    ))}
                </div>))}
            </div>
        ))}
        </div>
    </Col>;
}

function VenuesReport({ startDate, endDate, venues }) {
    return <Container>
        <h1>Venue bookings from { format_date(startDate) } to { format_date(endDate) }</h1>
        { 
            Object.keys(venues).length == 0 ?
            <h4>No bookings for this week. Check that venues are added correctly on the tour schedule.</h4> :
            <>
                <Row xs="6"> {
                Object.entries(venues).map(([vid, v]) => 
                    (<VenueWithBookings key={vid} name={v.name} 
                        email={v.contact_email} contactName={v.contact_name} bookings={v.booking_dates}/>)
                ) }
                </Row>
            </>
        }
    </Container>;
}

module.exports = { VenuesReport };