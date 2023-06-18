const { useState } = require("react");
const { Badge, Col, Row, Container, Button, Spinner } = require("react-bootstrap");
const { format_date, WEEKDAYS, format_time_12h, htmlLines } = require("./utils");

const RosterItem = ({ id, roster, onEdit, error }) => {
    let variant = roster.published ? 'success' : 'secondary';
    if (error === true) {
        variant = 'danger';
    }
    return <div className={`m-1 p-1 rounded-3 border border-${variant} bg-${variant}`} style={{['--bs-bg-opacity']: 0.25}}>
        <div className="fw-bold">{ format_time_12h(roster.time_start) } &mdash; { format_time_12h(roster.time_end) }</div>
        <div>{ roster.rider_name }</div>
        <div className="p-1 text-secondary">
            { htmlLines(roster.shift_notes) }
        </div>
    </div>
};

const TourRosterViewer = ({ tourArea, rosters, rosterErrors, onEdit, onSave, onAction, isLoaded, isSaved, saveStatus, setPage }) => {
    const [loading, setLoading] = useState(false);
    if (!rosters || !rosterErrors) return null;

    return <Container>
        <div className="TourRosterViewer">
        <h2>
            <span>
                Deputy Tour Rosters for&nbsp;
                {WEEKDAYS[(new Date(window.jsvars.tours_date)).getDay() - 1]} { format_date(window.jsvars.tours_date) }
            </span>
            &nbsp;
            <Badge key={1} className="" bg="none" style={{backgroundColor: tourArea.colour}}>
                { tourArea.display_name }
            </Badge>
        </h2>
        <div className="mb-1">
            <Button variant="secondary" onClick={() => {
                setLoading('back');
                onSave('open', (ok, response, action) => {
                    setLoading('back');
                    if (ok) {
                        setPage('schedules_editor');
                        window.history.replaceState(null, '', window.jsvars.urls.schedules_editor);
                        return response;
                    } else {
                        return { rosters, rosterErrors };
                    }
                })
            }}>
                { loading == 'back' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                Cancel &amp; back to Schedule
            </Button>

        </div>
        { rosterErrors.length == 0 ? null : <>
            <h4>Invalid rosters</h4>
            <Row className="g-5">
                { errorRosters.map((roster, i) => 
                    <Col key={i}>
                        <RosterItem roster={roster} error={true}/>
                    </Col>) }
            </Row>
        </> } 
        { rosters.length == 0 ? null : <>
            <h4>Rosters to be saved</h4>
            <Row className="g-5">
                { rosters.map((roster, i) => 
                    <Col key={i}>
                        <RosterItem roster={roster}/>
                    </Col>) }
            </Row>
        </> }
        { rosterErrors.length == 0 && rosters.length == 0 ? <h4>No rosters!</h4> : null }
        </div>
    </Container>;
};

module.exports = {
    TourRosterViewer,
};