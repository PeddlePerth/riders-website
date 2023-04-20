const { useState } = require("react");
const { Col, Badge, Button, Row, Spinner, Alert, ButtonGroup } = require("react-bootstrap");
const { CheckButton } = require("./components");
const EditableTextField = require("./EditableTextField");
const { useTimeout, useAjaxData, useEditableAjaxData, useForceUpdate } = require("./hooks");
const { format_short_date, firstDayOfWeek, addDays, parse_datetime, getWeekName } = require("./utils");


const AVAILABILITY_CHOICES = {'tours_am': 'AM Tours', 'tours': 'Tours', 'hustle': 'Hustle'};
const AvailabilityDayAdmin = ({ avlday, onChange })  => {
    const forceUpdate = useForceUpdate();
    const change = () => {
        onChange();
        forceUpdate();
    };

    if (!avlday) return null;
    if (!avlday.options) {
        avlday.options = {};
    }

    return <Col className="AvailabilityDayAdmin">
        <div className="fs-5 position-relative user-select-none mb-1 mt-1" onClick={() => {
                    avlday.enabled = !avlday.enabled;
                    change();
                }}>
            { format_short_date(avlday.date) }
            <Button
                className="position-absolute top-0 end-0"
                size="sm"
                variant={avlday.enabled ? 'success' : 'danger'}
                ><span className={avlday.enabled ? 'bi-check-lg' : 'bi-x-lg'}/></Button>
        </div>
        <EditableTextField className="mb-1" key={0} model={avlday} fieldName="notes" type="textarea" onCommit={change} label="Notes" />

        { avlday.enabled ? <>
            <Badge bg="info" className="mb-1">Select available shifts</Badge>
            <ButtonGroup vertical className="w-100">
            { Object.entries(AVAILABILITY_CHOICES).map(([optId, optTitle], i) => (
                <CheckButton key={i} variant="primary" size="sm" checked={avlday.options.includes(optId)}
                    text={<>{optTitle} {
                        avlday.riders_available && avlday.riders_available[optId] && avlday.riders_available[optId].length > 0 ? 
                            <Badge bg="info">{plural(avlday.riders_available[optId].length, ' rider', ' riders')} available</Badge> : null}
                        </>}
                    onChange={(val) => {
                    if (val) {
                        avlday.options.push(optId);
                    } else {
                        avlday.options = avlday.options.filter(oi => oi != optId);
                    }
                    change();
                }}/>)
            )}</ButtonGroup></> : <Badge bg="danger">(No shifts available)</Badge>
        }
    </Col>;
};

const AvailabilityWeekAdmin = ({ today, weekStart, avlDays, onChange, onSaveDefault }) => {
    const weekName = getWeekName(today, weekStart);
    
    if (!avlDays) return null;
    return <div className="AvailabilityWeekAdmin mb-5">
        <div>
            <span className="fs-5 fw-bold mb-1 me-1">{weekName}</span> &nbsp;
            <Button variant="danger" size="sm" onClick={onSaveDefault}><span className="bi-heart-fill"/> Save as Default</Button>
        </div>
        <Row className="mb-3" md={7} sm={4} xs={2}>
            { avlDays.map((avlDay, i) => <AvailabilityDayAdmin avlday={avlDay} key={i} onChange={onChange} />) }
        </Row>
    </div>;
};


const RiderAvailabilityAdmin = ({ initialDate }) => {
    const forceUpdate = useForceUpdate(); // Hack: must force full re-render on edit to keep UI updated
    
    const [data, {startDate}, dataSaved, isLoading, dataError, hasLock, save, reload, onEdit] = useEditableAjaxData(
        window.jsvars.data_url,
        window.jsvars.lock_url,
        5000,
        (data, {startDate, saveDefaultWeek}) => {
            return {
                date: startDate.valueOf(),
                weeks: data ? data.weeks : null,
                saveDefault: saveDefaultWeek,
            };
        },
        ({startDate}) => ({ // lock data
            date: startDate.valueOf(),
        }),
        null,
        () => {
            let startDate = new Date(initialDate);
            firstDayOfWeek(startDate);
            return {startDate};
        }
    );

    function addWeek() {
        // get start date for the next week after the last
        let nextWeek = startDate;
        if (data.weeks.length > 0) {
            nextWeek = new Date(data.weeks[data.weeks.length - 1].weekStart);
            addDays(nextWeek, 7);
        }

        data.weeks.push({
            weekStart: nextWeek.valueOf(),
            avlDays: data.weekTemplate.map((tmpl, i) => {
                let date = new Date(nextWeek);
                addDays(date, i);
                return {
                    ...tmpl,
                    date: date.valueOf(),
                };
            }),
        });
        
        onEdit();
        forceUpdate();
    }

    const header = <h1>Availabilities Admin</h1>;

    if (!data && isLoading) {
        return <>
            {header}
            <div className="text-center p-3"><Spinner animation="border"></Spinner></div>
        </>;
    } else if (dataError || data == null) {
        return <>
            {header}
            <Alert variant="danger">{dataError}</Alert>
        </>;
    }

    return <>
        {header}
        <p>Use this page to select which shifts riders can see on each day for the upcoming weeks.
            Click the dates or the <span className='bi-x'/>/<span className='bi-check'/> to show/hide days to riders.</p>
        <p>
            <b>For example:</b> Select <CheckButton checked size="sm" variant="primary" text="Hustle"/> so riders can mark themselves as available
            to hustle.</p>
        <div key={1} className="mb-2">
            <Button key={1} variant="primary" className="me-2" onClick={addWeek}>
                <span className="bi-plus"/> Add Week
            </Button>
            <Button key={2} variant="secondary" className="me-2" onClick={() => save({startDate: startDate})}>
                Save
            </Button>
            { dataSaved ? <Badge bg="success" className="me-2">Saved</Badge> : <Badge bg="secondary" className="me-2">Unsaved changes</Badge> }
            { hasLock ? null : <Badge bg="warning" className="fs-5">Another editor open: close or reload this tab!</Badge>}
        </div>
        { data.weeks.length == 0 ? <Alert variant="primary">No upcoming weeks for rider availabilities.</Alert> : <>
        <div key={2}>
            { data.weeks.map((week, i) => <AvailabilityWeekAdmin
                key={i}
                today={initialDate}
                weekStart={week.weekStart}
                avlDays={week.avlDays}
                onChange={() => {
                    onEdit();
                }}
                onSaveDefault={() => save({startDate: startDate, saveDefaultWeek: i})}
                />) }
        </div>
        { data.weeks.length == 0 ? null : <Button key={1} variant="primary" className="me-2" onClick={addWeek}>
                <span className="bi-plus"/> Add Week
            </Button> }
        </> }
    </>;
};

module.exports = {RiderAvailabilityAdmin, AVAILABILITY_CHOICES};