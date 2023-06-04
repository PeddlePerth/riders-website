const {
    Stack, Button, Row, Col, Badge
} = require('react-bootstrap');
const TourRow = require('./TourScheduleRow.js');
const TimespanLock = require('./TimespanLock.js');
const { join_bikes, count_bikes } = require('./BikesWidget.js');
const EditableTextField = require('./EditableTextField.js');
const { plural, format_time_12h } = require('./utils.js');
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

function getRiderList(text, allRiders) {
    let lines = text.split('\n');
    let riders = [];
    for (var l of lines) {
        if (!l) continue;
        let words = l.split(' ');
        let found = false;
        let numName = 0;
        var name = '';
        for (var i = 0; i < words.length; i++) {
            name = (name + ' ' + words[i]).trim().replaceAll('?', '');
            numName++;
            let matches = Object.values(allRiders).filter(rider => 
                rider.title && rider.title.toLowerCase().startsWith(name.toLowerCase())
            );
            let exact = matches.filter(rider => rider.title && rider.title.toLowerCase() == name.toLowerCase());
            if (matches.length == 1 || exact.length == 1) {
                let match = exact.length == 1 ? exact[0] : matches[0];
                riders.push([match.id, words.slice(numName).join(' ')]);
                found = true;
                break;
            }
        }
        if (!found) riders.push([null, l]);
    }
    console.log(riders);
    return riders;
}

function AvailableRidersInput({ allRiders, onChange }) {
    const [model, setModel] = useState({text: ''});
    const [riderList, setRiderList] = useState([]);

    return <div className="border rounded d-inline-block">
        <div className="p-1">Paste list of riders & notes from availability sheet below and fix any errors.</div>
        <Row xs={2} className="g-0">
            <Col className="p-2">
                <EditableTextField style={{minHeight: '50px'}}
                type="textarea"
                model={model}
                fieldName="text"
                onCommit={() => {
                    let lines = [];
                    for (var l of model.text.trim().split('\n')) {
                        let line = l.trim();
                        if (line) lines.push(line);
                    }
                    model.text = lines.join('\n');
                    let list = getRiderList(model.text, allRiders)
                    setRiderList(list);
                    onChange(list.filter(r => r[0] != null));
                }}
                />
            </Col>
            <Col className="p-2">
                <div>
                    { riderList.map(([rider, note], i) => 
                    <div key={i}>
                        <b>{ rider ? allRiders[rider].title : 'ERROR' }</b>&nbsp;{ note }
                    </div>)}
                </div>
            </Col>
        </Row>
    </div>;
}

const AvailableRider = ({ rider, notes, active, error }) => 
<div className={"AvailableRider p-1 me-1 mb-1 fs-6 rounded user-select-none d-inline-block" + 
    (active ? ' active' : '') + (error ? ' error' : '')}
    draggable={active} onDragStart={(e) => setRiderDragData(e, rider)}
    >
    <span key={0} className="fw-bold">{rider.title}</span>&nbsp;
    <span key={1} className="text-muted">{notes}</span>
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
            selectedSess: null,
        };

        let [riderTimes, conflictRiders, schedRiders] = this.getRiderTimeLocks();
        this.state.riderTimes = riderTimes;
        this.state.conflictRiders = conflictRiders;
        
        for (var rider_id of Object.keys(schedRiders)) {
            this.state.availableRiders.push([rider_id, 'from schedule']);
        }

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

        let riderTimes = {}, conflictRiders = {};
        Object.values(this.props.riders).forEach(r => {
            riderTimes[r.id] = new TimespanLock(first_session_start, last_session_end);
        });

        let schedRiders = {};
        // account for existing TourRiders in schedule data
        for (var tour_id of Object.keys(this.props.tours)) {
            let t = this.props.tours[tour_id];
            for (var r of t.riders) {
                let rt = riderTimes[r.rider_id];
                if (rt.is_locked_during(t.time_start, t.time_end)) {
                    let c = conflictRiders[r.rider_id] = (conflictRiders[r.rider_id] || []);
                    c.push([t.time_start, t.time_end]);
                }
                rt.lock_timespan(t.time_start, t.time_end);
                schedRiders[r.rider_id] = true;
            }
        }

        return [riderTimes, conflictRiders, schedRiders];
    } 

    // handle text data changes to tour rows
    onDataChange(row_id, field_name, value) {
        this.props.tours[row_id][field_name] = value;
        this.props.onEdit();
    }

    canAddRider(rider_id, time_start, time_end) {
        // check if rider can be added to _this_ tour
        if (time_start != null) {
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
        
        if (rider_id in this.state.conflictRiders) {
            let [riderTimes, conflictRiders, schedRiders] = this.getRiderTimeLocks();
            this.setState({
                riderTimes: riderTimes,
                conflictRiders: conflictRiders,
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
            let [riderTimes, conflictRiders, schedRiders] = this.getRiderTimeLocks();
            this.setState({
                riderTimes: riderTimes,
                conflictRiders: conflictRiders,
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

        const hasVenues = Object.values(this.props.tours).some(
            tour => (tour.venues && tour.venues.length > 0));
        return <div className="mx-3">
            <Row className="justify-content-center">
            { this.state.availability ? <Col xs={12} xl={2}>
            <div className="position-sticky overflow-scroll" style={{top: '0', height: '100vh'}}>
                { Object.keys(this.state.conflictRiders).length > 0 ? <>
                    <div className="fs-5 fw-bold mb-1 text-danger">Rider Conflicts</div>
                    { Object.entries(this.state.conflictRiders).map(([rider_id, conflicts], i) =>
                        conflicts.map(([timeStart, timeEnd], j) => <AvailableRider
                            key={j}
                            rider={this.props.riders[rider_id]} error
                            notes={`between ${format_time_12h(timeStart)} and ${format_time_12h(timeEnd)}`} />)
                    ) }
                </> : null }
                <div className="fs-5 fw-bold mb-1">Available Riders</div>

                { this.state.availableRiders.length > 0 ? 
                    <> 
                        <div className="fs-5 mb-1">
                            { this.state.selectedSess ? 
                            <span className="text-highlight">
                                {format_time_12h(sess.time_start)}&nbsp;-&nbsp;
                                {format_time_12h(sess.time_end)}
                            </span> : 'All day'}
                        </div>
                        {this.state.availableRiders.map(
                        ([riderId, notes]) =>
                            <AvailableRider key={riderId}
                                rider={this.props.riders[riderId]}
                                notes={notes}
                                active={sess ? this.canAddRider(riderId, sess.time_start, sess.time_end) : true}
                            />
                        )}
                </> : <>
                    <Badge className="fs-6 mb-1" bg="warning">Rider availability unknown</Badge>
                </>
                }
                <AvailableRidersInput allRiders={this.props.riders} onChange={(val) => {
                    let avlRiders = {};
                    val.forEach(([id, note]) => avlRiders[id] = note);
                    Object.values(this.props.tours).forEach(
                        t => t.riders.forEach(
                            tr => (tr.rider_id in avlRiders) ? null : avlRiders[tr.rider_id] = 'from schedule'));
                    this.setState({ availableRiders: Object.entries(avlRiders) })
                }} />
            </div>
            </Col> : null }

            <Col xs={12} xl={10}>
                <Stack className="TourScheduleEditor" direction="vertical">
                <Stack direction="horizontal" className="editor-menu my-1 py-1 position-sticky bg-light"
                    style={{ top: '0', height: '48px', zIndex: '11' }}>
                    <Button variant="primary" onClick={() => this.props.onSave(null, (ok) => {
                        if (ok) window.location.href = window.jsvars.urls.tours_for;
                    })}>
                        Save &amp; Return to Schedule
                    </Button>
                    { this.props.ajaxToolbar }
                    <CheckButton checked={this.state.availability} variant="secondary" className="ms-1"
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

module.exports = TourScheduleEditor;