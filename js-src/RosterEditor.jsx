const { useState, useMemo, useRef } = require("react");
const { Badge, ButtonGroup, Button, Spinner, Row, Col, Table, Alert } = require("react-bootstrap");
const { AutocompleteTextBoxV2 } = require("./AutocompleteTextBox");
const { BikesWidget } = require("./BikesWidget");
const { CalendarNav, getDateRange } = require("./CalendarNav");
const { MyButtonGroup, CheckButton } = require("./components");
const EditableTextField = require("./EditableTextField");
const { useAjaxData, useForceUpdate, useEditableAjaxData } = require("./hooks");
const { AVAILABILITY_CHOICES } = require("./RiderAvailabilityAdmin");
const { TimeInput } = require("./TimeInput");
const { firstDayOfWeek, format_time_12h, format_iso_date, get_weekday, format_date } = require("./utils");


const AvailableRider = ({ rider, choices, notes, active }) => 
<div className={"AvailableRider p-1 me-1 mb-1 fs-6 rounded user-select-none" + (active ? ' active' : '')}
    draggable={active} onDragStart={(e) => setRiderDragData(e, rider)}
    >
    <Row xs="auto" className="g-1 justify-content-between">
        <Col key={0} className="fw-bold">{rider.display_name}</Col>
        <Col key={1} className="ms-auto">
        { choices.sort((a, b) => b > a).map(c => 
            <Badge pill key={c} bg={c.includes('tours') ? 'info' : 'primary'} className="me-1">{AVAILABILITY_CHOICES[c]}</Badge>) }
        </Col>
    </Row>
    <span key={1} className="text-muted">{notes}</span>
</div>;


const RosterRiderWidget = ({ rr, allRiders, bikes, onClear }) => {

    return <div className="d-flex flex-wrap">
        <span className="fw-bold me-1 p-1">{rr.rider_id ? allRiders[rr.rider_id].display_name : null}</span>
        
        <MyButtonGroup key={1} className="align-self-end me-1" items={roleButtons} 
            onBtnClick={(btn) => {
                if (id == 'delete') onClear();
                //else 
            }}
        />

        <MyButtonGroup key={2} className="align-self-end mx-1"
            items={Object.entries(bikes).map(([bike, data]) => ({
                id: bike, title: data.name, 
                variant: (data.available > 0 ? (bike != 'bike' ? 'outline-info' : 'outline-primary') : 'outline-secondary')
            }))}

        />

    </div>;
};

// UI for RosterRider
const RosterRider = ({ slot, rr, allRiders, bikes, setRosterRider, canEdit=true }) => {
    const forceUpdate = useForceUpdate();
    const myRef = useRef(null);

    function changeRR(chgfunc) {
        if (!canEdit) return;
        // construct blank RosterRider if slot is empty
        var newRR = rr;
        if (rr) {
            chgfunc(newRR);
            setRosterRider(newRR);
            forceUpdate();
        } else {
            newRR = {
                'rr_id': null,
                'rider_id': null,
                'swap_from_id': null,
                'time_start': slot.timeStart,
                'bike': null,
                'role': null,
            };
            chgfunc(newRR);
            setRosterRider(newRR);
        }
    }

    let is_swap = rr && rr.swap_from_id != null;
    let timeStart = new Date(rr ? rr.time_start : slot.timeStart);
    // need to edit start time?? Nah?
    return <div className="RosterRider d-flex align-items-start my-1"
        ref={myRef}
        onDragOverCapture={(e) => {
            if (canEdit && getRiderFromDrop(e, allRiders)) {
                e.preventDefault();
                myRef.current.classList.add('dragover');
            }
        }}
        onDragEnterCapture={(e) => {
            if (canEdit && getRiderFromDrop(e, allRiders)) {
                e.preventDefault();
                myRef.current.classList.add('dragover');
            }
        }}
        onDragLeaveCapture={(e) => {
            myRef.current.classList.remove('dragover');
        }}
        onDropCapture={(e) => {
            myRef.current.classList.remove('dragover');
            let rider = getRiderFromDrop(e, allRiders);
            changeRR((rr) => rr.rider_id = rider.rider_id);
            e.preventDefault();
        }}
    >
        <TimeInput value={new Date(timeStart)} 
            onChange={(val) => changeRR((rr) => rr.time_start = val.valueOf())}/>
        <div key={0} className={"me-1 p-1 text-nowrap text-highlight" + (is_swap ? '-2' : '')}>
             {is_swap ? 'SWAP' : '@ WH'}
        </div>
        &nbsp;
        <div key={2} className="flex-shrink-1 align-self-center">
            { rr && rr.rider_id ?
            <RosterRiderWidget
                rr={rr}
                bikes={bikes}
                allRiders={allRiders}
                onClear={() => changeRR((rr) => rr.rider_id = null)}
            />
             : <AutocompleteTextBoxV2
                items={Object.values(allRiders)}
                initialFocus={false}
                selectedItem={rr && rr.rider_id ? allRiders[rr.rider_id] : null}
                onSelect={(item) => changeRR((rr) => rr.rider_id = item.rider_id)}
                titleAttr="display_name" />
            }
        </div>
    </div>;
};

// Represents a bike on the roster
const RosterRow = ({ slot, allRiders, bikes, onChange, deleteBadSlot }) => {
    const forceUpdate = useForceUpdate();

    return <div className="d-flex justify-content-between border-bottom px-1">
        <div>
            { deleteBadSlot ? <Badge bg="danger">Tours for this rider were changed/cancelled</Badge> : null }
            { slot.riders ? slot.riders.map((rr, j) => 
                // have RosterRider: use the data from there
                <RosterRider key={j} allRiders={allRiders} bikes={bikes} slot={slot} rr={rr} 
                    setRosterRider={(newRR) => {
                        slot.riders[j] = newRR;
                        onChange();
                    }}
                    canEdit={!deleteBadSlot}
                /> ) :
                // no RosterRider for this slot: empty widget
                <RosterRider allRiders={allRiders} bikes={bikes} slot={slot} rr={null} 
                    setRosterRider={(newRR) => {
                        slot.riders = [newRR];
                        forceUpdate();
                        onChange();
                    }}
                    canEdit={!deleteBadSlot}
                />
            }
        </div>
        <ButtonGroup size="sm" className="align-self-end">
            { !deleteBadSlot && slot.riders ? 
            <Button key={0} variant="outline-secondary" onClick={() => {
                let prev = slot.riders[slot.riders.length - 1];
                slot.riders.push({ // add an empty slot!
                    'swap_from_id': prev.rr_id || true, // is a swap but we may not have an ID yet
                    'bike': prev.bike,
                    'time_start': prev.time_start + (60*60*1000),
                }); 
                forceUpdate();
                onChange();
            }}>
                <span className="bi-plus-lg me-1"></span>
                Add Swap
            </Button> : null }

            { deleteBadSlot ? 
            <Button key={1} variant="outline-danger" onClick={() => deleteBadSlot()}>
                <span className="bi-x-lg me-1"></span>
                Delete
            </Button> : null }
        </ButtonGroup>
    </div>;
}

const RosterEditor = ({ initialDate, allRiders, bikeTypes }) => {
    const [
        rosterData,
        {selectedDay}, isSaved, rosterLoading, rosterDataError, hasLock, save, reload, onEdit] =
        useEditableAjaxData(
            window.jsvars.editor_url,
            window.jsvars.lock_url,
            null,
            (rosterData, {selectedDay}, isSave) => (
                isSave ? {
                    date: selectedDay.valueOf(),
                    // insert save data
                } : {
                    date: selectedDay.valueOf(),
                }
            ),
            ({selectedDay}) => ({ date: selectedDay.valueOf() }),
            null,
            () => ({ selectedDay: new Date(initialDate) })
        );

    const forceUpdate = useForceUpdate();
    function change() {
        onChange();
        forceUpdate();
    }

    const {rosterDay, rosterRiders, tours} = rosterData || {};

    // construct a list of actual roster slots, ordered by WH start time
    const [sortedSlots, ridersUnaccounted] = useMemo(
        () => getOrderedRosterSlots(rosterDay, rosterRiders, allRiders),
        [rosterDay, rosterRiders]);

    return <div className="border">
            <div key={0} 
                style={{backgroundColor: 'lime'}}
                className="d-flex justify-content-around border-bottom p-2">
                <div className="me-2 align-self-start">
                    <CheckButton checked={rosterDay.publish}
                        onChange={(val) => {
                            rosterDay.publish = val;
                            change();
                        }}
                        size="sm" text="Visible to riders"
                        className="m-1" />
                    <Button className="m-1" variant={!isSaved ? 'danger' : 'secondary'}
                        onClick={() => (isSaved ? save() : null) } >
                        {isSaved ? 'Saved' : 'Save'}
                    </Button>
                </div>
                <div className="text-center me-2">
                    <div key={0} className="mb-1 fs-5 fw-bold">
                        <span className="me-2">{ get_weekday(date, true) } { format_date(date) }</span>
                        { rosterDay.publish ? null : <Badge bg="danger">DRAFT</Badge> }
                    </div>
                    <div key={1} className="fs-6">
                        <EditableTextField
                            model={rosterDay}
                            onChange={change}
                            fieldName="notes"
                            type="textarea"
                            className="bg-light"
                        />
                    </div>
                </div>

                <div className="">
                    <BikesWidget model={rosterDay} fieldName="bikes" onChange={change} bikeTypes={bikeTypes} className="bg-light" />
                </div>
            </div>
            { ridersUnaccounted.map((riders, i) => 
                <RosterRow
                    key={i}
                    slot={{ riders: riders }}
                    deleteBadSlot={() => {
                        //onDelRider()
                    }}
                    allRiders={allRiders}

                />)
            }
            { sortedSlots.map((combinedSlot, i) => 
                <RosterRow
                    key={i}
                    slot={combinedSlot}
                    allRiders={allRiders}
                    bikes={bikeTypes}
                    onChange={() => onChange()}
                />)
            }
    </div>;
};

module.exports = {RosterEditor};