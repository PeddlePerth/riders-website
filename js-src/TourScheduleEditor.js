const {
    Stack, Button, Row, Col, Badge, Spinner
} = require('react-bootstrap');
const TourRow = require('./TourScheduleRow.js');
const TimespanLock = require('./TimespanLock.js');
const { join_bikes, count_bikes } = require('./BikesWidget.js');
const EditableTextField = require('./EditableTextField.js');
const { plural, format_time_12h, htmlLines, format_date, WEEKDAYS } = require('./utils.js');
const { useMemo, useState } = require('react');
const { CheckButton } = require('./components.js');

function TourScheduleGroup({ selected, session, onChange, info, children }) {
    // Session/group header: title (start/end times, tour type), number of bikes
    return <Row 
        className={'TourScheduleGroup position-sticky g-0' + (selected ? ' selected' : '')}
        style={{ top: '78px', zIndex: '9' }}
        xs={1} >
        <Col className='Header'>
            <Stack direction="horizontal" gap={3}>
                <EditableTextField
                    type="text"
                    model={session}
                    fieldName="title"
                    onChange={onChange}
                />
                { info }
            </Stack>
        </Col>
        { children }
    </Row>;
}

// use for dragstart event to set rider data (when dragging from availability widge or rider widget on schedule)
function setRiderDragData(event, rider) {
    event.dataTransfer.setData("application/json", JSON.stringify({
        rider_id: rider.rider_id
    }));
    //event.dataTransfer.setData("text/plain", rider.display_name);

}

function getRiderFromDrop(event, allRiders) {
    const data = event.dataTransfer.getData("application/json");
    try {
        let json = JSON.parse(data);
        if (json.rider_id in allRiders) return allRiders[json.rider_id];
    } catch (e) {}
    return null;
}

const AvailableRider = ({ rider, notes, state }) => 
<div className={"AvailableRider p-1 me-1 mb-1 fs-6 rounded user-select-none d-inline-block" + 
    (state ? ' ' + state : '')} // state is 'yes', 'no', 'maybe', 'error'
    draggable={state != 'error'} onDragStart={(e) => setRiderDragData(e, rider)}
    >
    { rider.is_core_rider ? <span className="bi-fire text-danger me-1"></span> : null }
    { rider.has_deputy ? <span className="bi-phone-vibrate-fill text-primary me-1"></span> : null }
    { rider.rider_class ? (rider.rider_class > '1' ? <span className="fw-bold text-success">{
        (rider.rider_class > '3' ? '$$' : '') +
        (rider.rider_class > '2' ? '$' : '')
     }</span> : <Badge bg="info">NOOB</Badge>) : null }
    <span key={0} className="ms-1 fw-bold">{rider.title}</span>&nbsp;
    <span key={1} className="text-muted">{htmlLines(notes)}</span>
</div>;

class TourScheduleEditor extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            riderTimes: {},
            availability: true,
            availableRiders: [],
            conflictRiders: {},
            riderTimes: {},
            riderTimesUnavail: {},
            selectedSess: null,
            loading: false,
        };

        let [riderTimes, riderTimesUnavail, conflictRiders, availRiders] = this.getRiderTimeLocks();
        this.state.riderTimes = riderTimes;
        this.state.riderTimesUnavail = riderTimesUnavail;
        this.state.conflictRiders = conflictRiders;
        // show available riders in order: by availability, then core riders, then by rider class
        this.state.availableRiders = availRiders;

        // add riders on the schedule to the availability list
        this.onDataChange = this.onDataChange.bind(this);
        this.canAddRider = this.canAddRider.bind(this);
        this.onAddRider = this.onAddRider.bind(this);
        this.onDelRider = this.onDelRider.bind(this);
        this.onChgRider = this.onChgRider.bind(this);
        this.onChgBikes = this.onChgBikes.bind(this);
        this.onChgGroup = this.onChgGroup.bind(this);
    }

    getRiderTimeLocks() {
        // populate riders & timespans
        const first_session_id = this.props.session_order[0];
        const last_session_id = this.props.session_order[this.props.session_order.length - 1];
        var first_session_start = 0, last_session_end = 0;
        if (first_session_id && last_session_id) {
            first_session_start = this.props.sessions[first_session_id].time_start - 1;
            last_session_end = this.props.sessions[last_session_id].time_end + 1;
        }

        // riderTimes is a TimespanLock for each rider to prevent double bookings
        let riderTimes = {};
        let riderTimesUnavail = {}; // track timespans where riders are unavailable (locked where available)
        // conflictRiders is dict of riders with conflicts
        let conflictRiders = {}; 

        Object.values(this.props.riders).forEach(r => {
            riderTimes[r.id] = new TimespanLock(first_session_start, last_session_end);
            riderTimesUnavail[r.id] = new TimespanLock(first_session_start, last_session_end);
            if (r.active != true || r.rider_class == null) {
                riderTimesUnavail[r.id].lock_timespan(first_session_start, last_session_end);
            }
        });

        for (var tour_id of Object.keys(this.props.tours)) {
            let t = this.props.tours[tour_id];
            for (var r of t.riders) {
                let rt = riderTimes[r.rider_id];
                if (rt.is_locked_during(t.time_start, t.time_end)) {
                    // conflict with another tour
                    let c = conflictRiders[r.rider_id] = (conflictRiders[r.rider_id] || []);
                    c.push(`tour conflict from ${format_time_12h(t.time_start)} to ${format_time_12h(t.time_end)}`);
                }

                rt.lock_timespan(t.time_start, t.time_end);
            }
        }

        // account for rider unavailability and check for conflicts with the prior tour schedule
        for (var [rider_id, time_off] of Object.entries(this.props.rider_time_off)) {
            if (!(rider_id in riderTimesUnavail)) continue;
            
            for (var ts of time_off) {
                if (ts.tour_id != null && ts.tour_id in this.props.tours) {
                    // the unavailability is specifically due to a tour which is on this schedule page
                    // therefore we ignore it here - will be dealt with above (see riderTimes)
                    continue;
                }
                let avl_start = ts.start < first_session_start ? first_session_start : ts.start;
                let avl_end = ts.end > last_session_end ? last_session_end : ts.end;

                // lock times when unavailable - check for overlaps and make sure all unavailabilities are locked
                if (riderTimesUnavail[rider_id].is_locked_during(avl_start, avl_end)) {
                    riderTimesUnavail[rider_id].unlock_timespan(avl_start, avl_end);
                }
                riderTimesUnavail[rider_id].lock_timespan(avl_start, avl_end); 
                
                // check for locked times when on tours
                if (!(ts.start > last_session_end || ts.end < first_session_start) && riderTimes[rider_id].is_locked_during(avl_start, avl_end)) {
                    // rider unavailable during some scheduled tour
                    let c = conflictRiders[rider_id] = (conflictRiders[rider_id] || []);
                    c.push(`unavailable from ${format_time_12h(ts.start)} to ${format_time_12h(ts.end)}`);
                }
            }
        }

        // list of avialable rider data: [rider_id, status(yes/no/maybe), description(str), rating(int)]
        var availRiders = Object.keys(this.props.riders).map((rider_id) => {
            let rdUnavail = riderTimesUnavail[rider_id];
            if (rdUnavail.lock_times.length == 0) {
                return [rider_id, 'yes', '', 100];
            } else if (!rdUnavail.is_available_during(first_session_start, last_session_end)) {
                return [rider_id, 'no', 'not available', 0];
            }
            let unavailTimes = rdUnavail.get_timespans();
            let notes = unavailTimes.map(ts => {
                if (ts[0] == null) return `before ${format_time_12h(ts[1])}`;
                else if (ts[1] == null) return `after ${format_time_12h(ts[0])}`;
                else return `from ${format_time_12h(ts[0])} to ${format_time_12h(ts[1])}`;
            });
            return [rider_id, 'maybe', notes, 10];
        });

        availRiders = availRiders.sort(
            (a, b) => {
                if (a[3] != b[3]) return b[3] - a[3]; // by availability preference
                let rider_a = this.props.riders[a[0]], rider_b = this.props.riders[b[0]];
                if (rider_a.is_core_rider != rider_b.is_core_rider) 
                    return rider_a.is_core_rider ? -1 : 1;
                if (rider_a.has_deputy != rider_b.has_deputy)
                    return rider_a.has_deputy ? -1 : 1;
                if (rider_a.rider_class != rider_b.rider_class) 
                    return rider_a.rider_class > rider_b.rider_class ? -1 : 1;
                return 0;
            }
        );

        return [riderTimes, riderTimesUnavail, conflictRiders, availRiders];
    }

    // handle text data changes to tour rows
    onDataChange(row_id, field_name, value) {
        this.props.tours[row_id][field_name] = value;
        this.props.onEdit();
    }

    canAddRider(rider_id, time_start, time_end, notUnavailable) {
        // check if rider can be added to _this_ tour
        if (time_start != null) {
            if (notUnavailable) {
                if (this.state.riderTimesUnavail[rider_id].is_locked_during(time_start, time_end))
                    return false;
            }
            return !this.state.riderTimes[rider_id].is_locked_during(time_start, time_end);
        }

        // check if rider can be added to _any_ tours
        for (var tour_id of Object.keys(this.props.tours)) {
            let t = this.props.tours[tour_id];
            if (!this.state.riderTimes[rider_id].is_locked_during(t.time_start, t.time_end))
                return true;
        }
        return false;
    }

    onAddRider(tour_id, rider_id) {
        let t = this.props.tours[tour_id];

        t.riders = t.riders.concat([{ rider_id: rider_id, rider_role: null }]);
        
        if (rider_id in this.state.conflictRiders ||
            this.state.riderTimesUnavail[rider_id].is_locked_during(t.time_start, t.time_end)) {
            let [riderTimes, riderTimesUnavail, conflictRiders, availRiders] = this.getRiderTimeLocks();
            this.setState({
                riderTimes: riderTimes,
                riderTimesUnavail: riderTimesUnavail,
                conflictRiders: conflictRiders,
                availableRiders: availRiders,
            });
        } else {
            this.state.riderTimes[rider_id].lock_timespan(t.time_start, t.time_end);
        }

        this.props.onEdit();
    }

    onDelRider(tour_id, rider_id) {
        let t = this.props.tours[tour_id];
        t.riders = t.riders.filter(el => (el.rider_id != rider_id));

        if (rider_id in this.state.conflictRiders) {
            let [riderTimes, riderTimesUnavail, conflictRiders, availRiders] = this.getRiderTimeLocks();
            this.setState({
                riderTimes: riderTimes,
                riderTimesUnavail: riderTimesUnavail,
                conflictRiders: conflictRiders,
                availableRiders: availRiders,
            });
        } else {
            this.state.riderTimes[rider_id].unlock_timespan(t.time_start, t.time_end);
        }

        this.props.onEdit();
    }

    onChgRider(tour_id, rider_id, role) {
        let riders = this.props.tours[tour_id].riders;
        riders.find(r => (r.rider_id == rider_id)).rider_role = role;
        this.props.onEdit();
    }

    onChgBikes(tour_id, bikes) {
        this.props.tours[tour_id].bikes = bikes;
        this.props.onEdit();
    }

    onChgGroup(sess_id) {
        // do nothing - mark as changed only
        this.props.onEdit();
    }

    render() {
        let sess = this.state.selectedSess ? this.props.sessions[this.state.selectedSess] : null;
        let area = window.jsvars.tour_areas[window.jsvars.tour_area_id];

        const hasVenues = Object.values(this.props.tours).some(
            tour => (tour.venues && tour.venues.length > 0));
        return <div className="mx-3">
            <h2>
                <Badge bg="none" style={{ backgroundColor: area.colour }}>
                    { area.name }
                </Badge>
                Editing schedule for {WEEKDAYS[(new Date(window.jsvars.tours_date)).getDay() - 1]} { format_date(window.jsvars.tours_date) }
            </h2>
            <Row className="justify-content-center">
            { this.state.availability ? <Col xs={12} xl={2}>
            <div className="position-sticky overflow-scroll" style={{top: '0', maxHeight: '100vh'}}>
                { Object.keys(this.state.conflictRiders).length > 0 ? <>
                    <div className="fs-5 fw-bold mb-1 text-danger">Rider Conflicts</div>
                    { Object.entries(this.state.conflictRiders).map(([rider_id, conflicts], i) =>
                        conflicts.map((notes, j) => <AvailableRider
                            key={j}
                            rider={this.props.riders[rider_id]}
                            state="error"
                            notes={notes} />)
                    ) }
                </> : null }
                <div key={1} className="fs-5 fw-bold mb-1">Available Riders</div>
                <div key={2} className="fs-5 mb-1">
                    { this.state.selectedSess ? 
                    <span className="text-highlight">
                        {format_time_12h(sess.time_start)}&nbsp;-&nbsp;
                        {format_time_12h(sess.time_end)}
                    </span> : 'All day'}
                </div>
                { this.state.availableRiders.map(r => <AvailableRider 
                        key={r[0]} 
                        rider={this.props.riders[r[0]]} 
                        state={r[1] != 'no' && sess != null ? 
                            (this.canAddRider(r[0], sess.time_start, sess.time_end, true) ? 'yes' : null)
                            : r[1]}
                        notes={r[2]}
                    />)}
            </div>
            </Col> : null }

            <Col xs={12} xl={10}>
                <Stack className="TourScheduleEditor" direction="vertical">
                <Stack direction="horizontal" className="editor-menu my-1 py-1 position-sticky bg-light"
                    style={{ top: '0', height: '48px', zIndex: '11' }}>
                    <Button key={2} variant="primary" className="me-1" 
                    onClick={() => {
                        this.props.onSave('close', (ok, response) => {
                            if (ok) {
                                window.onbeforeunload = null;
                                window.location.href = window.jsvars.urls.tours_for;
                            } else {
                                this.setState({loading: false});
                            }
                            return {
                                ...this.props, // ignore empty POST data response and re-use already loaded data
                            };
                        });
                        this.setState({loading: 'save-view'});
                    }}>
                        { this.state.loading == 'save-view' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                        Save &amp; View Schedule
                    </Button>
                    <Button key={4} variant="primary" className="me-1" onClick={() => {
                        this.props.onSave('get_rosters', (ok, response) => {
                            if (ok) {
                                window.history.replaceState(null, '', window.jsvars.urls.roster_admin);
                                this.props.setPage('roster_admin');
                                return {
                                    ...this.props,
                                    ...response,
                                };
                            } else {
                                this.setState({ loading: false });
                                return {
                                    ...this.props, // keep existing data in case of error
                                };
                            }
                        });
                        this.setState({ loading: 'get-rosters' });
                    }}>
                        { this.state.loading == 'get-rosters' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                        <i className="bi-phone-vibrate-fill me-1"/>Save &amp; View Rosters
                    </Button>
                    <Button key={1} variant={ this.props.isSaved ? 'secondary' : 'success' } className="me-1"
                        onClick={() => {
                            this.props.onSave('save', (ok, response) => {
                                this.setState({ loading: false });
                                if (ok) { // save response won't update Deputy unavailability, keep the previously loaded data
                                    return {
                                        ...response,
                                        rider_time_off: this.props.rider_time_off,
                                    };
                                } else {
                                    return { ... this.props }; // keep existing data but show save error
                                }
                            });
                            this.setState({ loading: 'save' });
                        }}>
                        { this.state.loading == 'save' ? <Spinner animation="border" className="me-1" size="sm"/> : null }
                        Save</Button>
                    <Badge bg="info" className="me-1" key={3}>{ this.props.saveStatus }</Badge>
                    { this.props.errorMsg ? <Badge bg="danger" className="me-1" key={44}>{ this.props.errorMsg }</Badge> : null }
                    <CheckButton checked={this.state.availability} variant="secondary" className="me-1"
                        onChange={(val) => this.setState({availability: val})} text="Show Available Riders" />
                </Stack>
                <div key={0}>
                    <ul className="tips">
                        <li key={-1}>Hold Ctrl key and click to revert cells to the original value (<span className="bi-command"/> on Mac)</li>
                        { !hasVenues ? [
                            <li key={1}>Add stops to a tour using the preset buttons in under Notes.</li>
                        ] : [
                            <li key={0}>Type &amp; select a venue by name.</li>,
                            <li key={1}>Drag &amp; drop stops to swap.</li>,
                            <li key={2}>
                                Switch between Venue (<span className="bi-stoplights-fill"/>),
                                Transit (<span className="bi-bicycle"/>) and
                                Activity (<span className="bi-megaphone-fill"/>) using the buttons.
                            </li>
                        ] }
                    </ul>
                </div>
                <Row className="Header g-0 position-sticky" style={{top: '48px', zIndex: '10', height: '30px'}}>
                    <Col key={1} xs={8}>
                        <Row className="g-0">
                            <Col key={1} xs={3}>Riders ({this.props.tours_date_formatted})</Col>
                            <Col key={2} xs={3}>Customer Name</Col>
                            <Col key={3} xs={2}>Customer Phone</Col>
                            <Col key={4}>Quantity</Col>
                            <Col key={5}>Pickup at</Col>
                        </Row>
                    </Col>
                    <Col key={2} xs={4}>
                        Notes
                    </Col>
                </Row>

                { this.props.session_order.map(
                    (sess_id) => 
                    <div key={sess_id} 
                        className={this.state.selectedSess === sess_id ? 'TSEGroupSelected' : ''}
                        onClick={() => this.state.availability ? this.setState({ selectedSess: sess_id }) : null}>
                        
                        <TourScheduleGroup
                            key={'s' + sess_id}
                            session={this.props.sessions[sess_id]}
                            onChange={ () => this.props.onEdit() }
                            info={<span>{plural(
                                count_bikes(join_bikes(this.props.sessions[sess_id].tour_ids.map(
                                    tour_id => this.props.tours[tour_id].bikes))), ' rider', ' riders')}</span> }
                            />
                        { this.props.sessions[sess_id].tour_ids.map(
                        (tour_id) => <TourRow 
                            key={'t' + tour_id}
                            tour={this.props.tours[tour_id]}
                            bikeTypes={this.props.bike_types}
                            onEdit={this.props.onEdit}
                            onAddRider={this.onAddRider}
                            onDelRider={this.onDelRider}
                            onChgRider={this.onChgRider}
                            canAddRider={this.canAddRider}
                            onChgBikes={this.onChgBikes}
                            allRiders={this.props.riders}
                            allVenues={this.props.venues}
                            venuePresets={this.props.venue_presets}
                        />
                        ) }
                    </div>
                )}
            </Stack>
        </Col>
        </Row></div>;
    }
}

// make an intermediate component for unpacking ajax tour data props correctly
const TourScheduleEditorAjax = ({ ajaxResponse, staticData, onAction, onSave, onEdit, saveStatus, isSaved, isLoaded, errorMsg, setPage }) => {
    let data = ajaxResponse != null ? {...ajaxResponse} : {};
    if (staticData) {
        for (var [key, val] in Object.entries(staticData)) {
            ajax[key] = val;
        }
    }
    if (isLoaded && ajaxResponse) {
        return <TourScheduleEditor
            onAction={onAction}
            onSave={onSave}
            onEdit={onEdit}
            saveStatus={saveStatus}
            isSaved={isSaved}
            isLoaded={isLoaded}
            errorMsg={errorMsg}
            tours={data.tours}
            riders={data.riders}
            venues={data.venues}
            venue_presets={data.venue_presets}
            bike_types={data.bike_types}
            tours_date_formatted={data.tours_date_formatted}
            setPage={setPage}
        />;
    }
    return null;
}



module.exports = TourScheduleEditor;