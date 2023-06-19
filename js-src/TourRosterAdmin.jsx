const { useState } = require("react");
const { Badge, Col, Row, Container, Button, Spinner } = require("react-bootstrap");
const { CheckButton } = require("./components");
const { format_date, WEEKDAYS, format_time_12h, htmlLines } = require("./utils");

const ModifiedBadge = () => <Badge bg="primary" className="me-1"><i className="fs-5 me-1 bi-cloud-upload"/>Modified</Badge>;
const AddedBadge = () => <Badge bg="success" className="me-1"><i className="fs-5 me-1 bi-cloud-plus"/>New</Badge>;
const DeletedBadge = () => <Badge bg="danger" className="me-1"><i className="fs-5 me-1 bi-cloud-slash"/>Deleted</Badge>;
const UnchangedBadge = () => <Badge bg="secondary" className="me-1"><i className="fs-5 me-1 bi-cloud-check"/>Unchanged</Badge>;
const OKBadge = () => <Badge bg="success" className="me-1"><i className="fs-5 me-1 bi-cloud-check"/>OK</Badge>;

const RosterItem = ({ id, roster, onEdit, error }) => {
    let variant = roster.published ? 'success' : 'secondary';
    let icon = null;
    let readonly = roster.source_row_state == 'deleted';
    // row states: live, deleted, changed, unchanged
    // row error states: add_error, update_error, delete_error
    if (error === true) {
        variant = 'danger';
        if (roster.source_row_state == 'add_error') icon = <AddedBadge/>;
        else if (roster.source_row_state == 'update_error') icon = <ModifiedBadge/>;
        else if (roster.source_row_state == 'delete_error') icon = <DeletedBadge/>;
    } else {
        if (roster.source_row_state == 'added') icon = <AddedBadge/>;
        else if (roster.source_row_state == 'changed') icon = <ModifiedBadge/>;
        else if (roster.source_row_state == 'unchanged') icon = <UnchangedBadge/>;
        else if (roster.source_row_state == 'deleted') icon = <DeletedBadge/>;
        else if (roster.source_row_state == 'live') icon = <OKBadge/>;
    }

    return <div className={`m-1 p-1 rounded-3 border border-${variant} bg-${variant}`} style={{['--bs-bg-opacity']: 0.25}}>
        <div className="fw-bold lh-base d-flex align-items-center">
            <span key={1} className="py-1 me-2">{ format_time_12h(roster.time_start) } &mdash; { format_time_12h(roster.time_end) }</span>
            <span key={2} className="me-2">{ icon }</span>
            { error || readonly ? null : <CheckButton checked={roster.published} onChange={(val) => {
                if (error) return;
                roster.published = val;
                onEdit();
             }} text="Publish" className="ms-auto"/> }
        </div>
        <div>{ roster.rider_name }</div>
        <div className="p-1 text-secondary">
            { htmlLines(roster.shift_notes) }
        </div>
    </div>
};

const TourRosterViewer = ({ tourArea, rosters, rosterErrors, onEdit, onSave, onAction, isLoaded, isSaved, saveStatus, errorMsg, setPage }) => {
    const [loading, setLoading] = useState(false);
    if (!rosters || !rosterErrors) return null;

    let syncedRosters = rosters.filter(r => r.source_row_state == 'unchanged' || r.source_row_state == 'live');
    let chgRosters = rosters.filter(r => r.source_row_state != 'unchanged' && r.source_row_state != 'live');

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
            <Button key={1} variant="secondary" className="me-1" onClick={() => {
                setLoading('back');
                onSave('open', (ok, response, action) => {
                    if (ok) {
                        window.onbeforeunload = null;
                        window.location.href = window.jsvars.urls.schedules_editor;
                    } else {
                        setLoading(false);
                    }
                    return { rosters, rosterErrors };
                });
            }}>
                { loading == 'back' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                Cancel &amp; back to editor
            </Button>
            <Button variant="success" className="me-1" onClick={() => {
                setLoading('reload');
                onSave('get_rosters', (ok, response, action) => {
                    setLoading(false);
                    if (!ok) return {rosters, rosterErrors};
                    return response;
                })
            }}>
                { loading == 'reload' ? <Spinner animation="border" className="me-1" size="sm"/> : <i className="bi-arrow-clockwise me-1"/> }
                Reload
            </Button>
            <Button key={2} variant="primary" className="me-1" onClick={() => {
                setLoading('save');
                onSave('save_rosters', (ok, response, action) => {
                    setLoading(false);
                    if (ok) {
                        return response;
                    } else {
                        return { rosters, rosterErrors }; // keep last good data in case of error
                    }
                });
            }}>
                { loading == 'save' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                Save to Deputy
            </Button>
            <Button key={3} variant="primary" className="me-1" onClick={() => {
                setLoading('save_return');
                onSave('save_rosters', (ok, response, action) => {
                    if (ok) {
                        window.onbeforeunload = null;
                        window.location.href = window.jsvars.urls.tours_for;
                        return response;
                    } else {
                        setLoading(false);
                        return { rosters, rosterErrors };
                    }
                });
            }}>
                { loading == 'save_return' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                Save &amp; view Schedule
            </Button> 
            <Badge bg="info" className="me-1" key={4}>{ saveStatus }</Badge>
            { errorMsg ? <Badge bg="danger" className="me-1" key={5}>{ errorMsg }</Badge> : null }
        </div>
        { rosterErrors.length == 0 ? null : <>
            <h4 className="mt-3">Invalid rosters</h4>
            <Row className="g-5">
                { rosterErrors.map((roster, i) => 
                    <Col key={i}>
                        <RosterItem roster={roster} error={true}/>
                    </Col>) }
            </Row>
        </> } 
        { chgRosters.length == 0 ? null : <>
            <div className="mt-3 d-flex align-items-center">
                <h4>Rosters to update</h4>
            </div>
            <Row className="g-5">
                { chgRosters.map((roster, i) => 
                    <Col key={i}>
                        <RosterItem roster={roster} onEdit={onEdit}/>
                    </Col>) }
            </Row>
        </> }
        { syncedRosters.length == 0 ? null : <>
            <h4 className="mt-3">Rosters already in Deputy</h4>
            <Row className="g-5">
                { syncedRosters.map((roster, i) => 
                    <Col key={i}>
                        <RosterItem roster={roster} onEdit={onEdit}/>
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