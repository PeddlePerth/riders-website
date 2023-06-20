const { useState } = require("react");
const { Stack, Row, Col, Badge } = require("react-bootstrap");
const EditableTextField = require("./EditableTextField");
const { AutocompleteTextBoxV2 } = require('./AutocompleteTextBox');
const { MyButtonGroup, CheckButton } = require("./components");
const { format_time_12h, htmlLines, parse_datetime } = require("./utils");

/** Generate venues summary text from tour and dict of allVenues (keyed by venue ID) */
function get_venues_summary(tour, allVenues) {
    var time = parse_datetime(tour.time_start);
    var vsum = [`${format_time_12h(time)} - Tour start`];
    var prev;
    for (var i = 0; i < tour.venues.length; i++) {
        const tv = tour.venues[i];
        const vinfo = tv.venue_id ? allVenues[tv.venue_id] : null;
        const time_arrive = time;
        const time_depart = new Date(time.getTime() + (tv.duration * 60 * 1000));

        // translated from schedules.py get_venues_summary (at revision a135dcc)
        if (tv.activity == 'transit') {
            if (tv.notes) {
                if (prev && prev.activity == 'venue') {
                    vsum[vsum.length - 1] += '. ' + tv.notes;
                } else {
                    vsum.push(`${format_time_12h(time_arrive)} - ${tv.notes}`);
                }
            }
        } else if (tv.activity == 'venue' || tv.activity == 'activity') {
            if (vinfo) {
                if (tv.notes) {
                    let notes = tv.notes.startsWith('[') ? tv.notes : ` - ${tv.notes}`;
                    vsum.push(`${format_time_12h(time_arrive)} - Arrive ${vinfo.name} ${notes}`);
                } else {
                    vsum.push(`${format_time_12h(time_arrive)} - Arrive ${vinfo.name}`);
                }
                if (i < tour.venues.length - 1) {
                    vsum.push(`${format_time_12h(time_depart)} - Depart ${vinfo.name_short}`);
                }
            } else {
                if (prev && prev.activity == 'venue') {
                    vsum[vsum.length - 1] += `, ${tv.notes}`;
                } else {
                    vsum.push(`${format_time_12h(time_arrive)} - ${tv.notes}`);
                }
            }
        }
        prev = tv;
        time = time_depart;
    }

    vsum.push(`${format_time_12h(tour.time_end)} - Tour finish`);
    return vsum;
}


// inspired by https://dev.to/colinmcd01/drag-drop-re-ordering-using-html-and-react-974
const DragOrderRow = ({ items, setItems, itemClass, rowWidth=5}) => {
    const [draggingId, setDraggingId] = useState(null);
    const [dragoverId, setDragoverId] = useState(null);

    const dragFromRight = dragoverId < draggingId;

    function handleDragOver(e, id) {
        e.preventDefault();
        setDragoverId(id);
    }

    // drop event fires BEFORE dragend 
    // see https://stackoverflow.com/questions/38111946/is-there-a-defined-ordering-between-dragend-and-drop-events
    function handleDrop(e, dropId) {
        if (draggingId === null || dropId === draggingId || items.length < 2) return;
        // reorder dragged item with dropped item
        const newItems = [];
        for (var i = 0; i < items.length; i++) {
            if (dropId < draggingId) { // dropId < draggingId, insert dragged item to left of drop target
                if (i == dropId) {
                    newItems.push(items[draggingId]);
                } else if (i > dropId && i <= draggingId) {
                    newItems.push(items[i - 1]);
                } else if (i > draggingId || i < dropId) {
                    newItems.push(items[i]);
                }
            } else { // dropId > draggingId, insert dragged item to right of drop target
                if (i == dropId) {
                    newItems.push(items[draggingId]);
                } else if (i < dropId && i >= draggingId) {
                    newItems.push(items[i + 1]);
                } else if (i > dropId || i < draggingId) {
                    newItems.push(items[i]);
                }
            }
        }
        
        //console.log('handleDrop', items, newItems);
        if (setItems) setItems(newItems.map(itm => itm.item));
    }

    function handleDragStart(e, id) {
        setDraggingId(id);
    }

    return <Row className="DragOrderRow g-0" xs={rowWidth}>
        {
        items.map((item, id) => 
            <Col key={item.key}
                className={"Draggable" + (itemClass ? ' ' + itemClass : '') +
                    (draggingId === id ? ' dragging' : '') +
                    (dragoverId === id && dragoverId !== draggingId ? (
                        dragFromRight ? ' dragover-left' : ' dragover-right') : '')}
                draggable={true}
                onDragEnter={(e) => setDragoverId(id)}
                onDragOver={(e) => handleDragOver(e, id)}
                onDragLeave={(e) => {
                    setDragoverId(null);
                }}
                onDrop={(e) => handleDrop(e, id)}
                onDragStart={(e) => handleDragStart(e, id)}
                onDragEnd={(e) => {
                    setDraggingId(null);
                    setDragoverId(null);
                }}
                >
                {item.element}
            </Col>)
        }
    </Row>;
};


const TV_TYPES = [
    { id: 'venue', icon: 'bi-stoplights', variant: 'outline-secondary' },
    { id: 'transit', icon: 'bi-bicycle', variant: 'outline-success' },
    { id: 'activity', icon: 'bi-megaphone', variant: 'outline-primary' },
    { id: 'del', icon: 'bi-trash', variant: 'outline-danger' },
    { id: 'duplicate', icon: 'bi-plus', variant: 'outline-success' },
];

function TourVenueV2({ tv, allVenues, onChange, onDelete, onDuplicate, order }) {
    //<span key={2} className="bi-signpost mx-1"></span>
    return <Stack className={"m-1 TourVenue " + tv.activity} direction="vertical">
        {
        (tv.activity !== 'transit' && tv.activity !== 'activity') ? 
        <div key={1} className="d-flex align-items-center">
            <Badge pill key={1} bg="success" className="mx-1">{ order }</Badge>
            <AutocompleteTextBoxV2
                items={Object.values(allVenues)}
                titleAttr="name"
                selectedItem={tv.venue_id ? allVenues[tv.venue_id] : null}
                initialFocus={false}
                onSelect={(item) => {
                    //console.log('selected', item);
                    if (item) {
                        tv.venue_id = item.id;
                        const notes = allVenues[item.id].notes;
                        if (notes) {
                            tv.notes = "[" + allVenues[item.id].notes + "]"; // autofill the specials!
                        } else {
                            tv.notes = "";
                        }
                    } else {
                        tv.venue_id = null;
                    }
                    onChange();
                }}
                className="flex-grow-1"
                />
        </div> : 
        <div key={1}>
            <Badge key={1} pill bg="success">{order}</Badge>
            <span key={2} className="title mx-1">{ tv.activity === 'transit' ? 'Transit' : 'Activity' }</span>
        </div>
        }
        <div key={2} className="d-flex my-1">
            <span className="bi-stopwatch mx-1"></span>
            <EditableTextField
                type="mins"
                model={tv}
                fieldName="duration"
                onCommit={onChange}
                className="flex-grow-1"
                />
            <MyButtonGroup 
                items={TV_TYPES}
                value={tv.activity}
                onBtnClick={(val) => {
                    if (val == 'del') {
                        onDelete();
                    } else if (val == 'duplicate') {
                        onDuplicate();
                    } else {
                        tv.activity = val;
                        if (val != 'venue') {
                            tv.venue_id = null; // clear venue
                        }
                        onChange();
                    }
                }}
            />
        </div>
        <div key={3} className="d-flex">
            <span className="bi-text-paragraph mx-1"></span>
            <EditableTextField
                type="textarea"
                model={tv}
                fieldName="notes"
                onCommit={onChange}
                className="flex-grow-1"
                />
        </div>
    </Stack>;
}

var nextVenueKey = 1;

function updateNotes(notes, venueLines){
    var lines = notes.split('\n');
    venueLines = venueLines || [];
    var start, end;
    for (var i = 0; i < lines.length; i++) {
        let ll = lines[i].toLowerCase();
        if (ll.includes('tour fin')) end = i;
        else if (ll.includes('tour start')) start = i;
    }

    if (start !== undefined && end !== undefined && end > start) {
        lines.splice(start, (end - start + 1), ...venueLines);
    } else {
        lines = venueLines.concat(lines);
    }
    return lines.join('\n');
}

function TourVenuesEditorV2({ tour, allVenues, onChange }) {
    tour.venues.forEach((tv) => {
        if (tv.key === undefined) {
            tv.key = nextVenueKey++;
        }
    });
    // do naughty thing to make venue text work
    const auto_values = tour.field_auto_values = (tour.field_auto_values || {});
    auto_values.venue_notes = get_venues_summary(tour, allVenues).join('\n');

    function updateVenueSummary() {
        // update the venue text automatically if the venues are changed, and the text has not been changed
        if (!(tour.venue_notes) || tour.venue_notes == auto_values.venue_notes) {
            tour.venue_notes = get_venues_summary(tour, allVenues).join('\n');
        }
    }

    return <div className="TourVenuesEditor">
        <Row className="g-0">
            <Col key={1} xs="10"><DragOrderRow 
            items={ tour.venues.map((tv, i) => ({
                element: <TourVenueV2 
                    tv={tv}
                    order={i}
                    allVenues={allVenues}
                    onChange={() => {
                        updateVenueSummary();
                        onChange();
                    }}
                    onDelete={() => {
                        tour.venues = tour.venues.filter((tva) => tva !== tv);
                        updateVenueSummary();
                        onChange();
                    }}
                    onDuplicate={() => {
                        tour.venues.splice(i + 1, 0, {
                            id: null,
                            venue_id: tv.venue_id,
                            activity: tv.activity,
                            notes: tv.notes,
                            duration: tv.duration,
                        });
                        updateVenueSummary()
                        onChange();
                    }}
                    />,
                item: tv,
                key: tv.key,
            })) }
            setItems={ (items) => {
                items.forEach((item, index) => item.venue_order = index);
                tour.venues = items;
                updateVenueSummary();
                onChange();
            }}
            /></Col>
            <Col key={2} xs="2">
                <EditableTextField 
                    type="textarea"
                    model={tour}
                    fieldName="venue_notes"
                    onChange={() => { updateVenueSummary(); onChange(); }}
                />
            </Col>
        </Row>
    </div>;//<div key={2}>{ htmlLines(venuesSummary) }</div>
}

// generate a list of JSON-TourVenues from a VENUE_PRESETS_SETTING item
function makeVenues(tour_id, preset) {
    const venues = preset.map((pv, i) => ({
            id: null,
            tour_id: tour_id,
            venue_id: null,
            activity: pv.type || 'venue',
            duration: pv.duration || 15,
            notes: pv.notes || '',
        }));
    console.log('tour venues for ' + tour_id, venues);
    return venues;
}


module.exports = { TourVenuesEditorV2, makeVenues, get_venues_summary };