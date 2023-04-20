const { Row, Col, ButtonGroup, Spinner, Badge, Alert } = require("react-bootstrap");
const { CheckButton } = require("./components");
const EditableTextField = require("./EditableTextField");
const { useEditableAjaxData, useForceUpdate } = require("./hooks");
const { AVAILABILITY_CHOICES } = require("./RiderAvailabilityAdmin");
const { getWeekName, format_short_date } = require("./utils");

const AvlDay = ({ week, day, onChange }) => {
    const forceUpdate = useForceUpdate();

    return <Col className="ps-1 pe-1">
        <div className="fw-bold fs-5">{format_short_date(day.date)}</div>
        <div className="fs-6">{day.notes}</div>
        { day.enabled ? <>
        <ButtonGroup vertical className="w-100 mb-1">
            { day.options.map((opt, oi) => <CheckButton
                key={oi}
                text={AVAILABILITY_CHOICES[opt]}
                checked={day.choices.includes(opt)}
                onChange={(val) => {
                    if (val) {
                        day.choices.push(opt);
                    } else {
                        day.choices = day.choices.filter(dc => dc != opt);
                    }
                    week.blank = false;
                    onChange();
                    forceUpdate();
                }}
                />
            )}
        </ButtonGroup>
        <EditableTextField
            type="textarea"
            fieldName="rider_notes"
            model={day}
            onCommit={() => {
                week.blank = false;
                onChange();
                forceUpdate();
            }}
            className="mb-1"
            />
        </> : <Badge bg="danger">No shifts available</Badge> }
    </Col>;
}

const AvlWeek = ({ today, week, onChange }) => {
    const forceUpdate = useForceUpdate();

    return <div className={
        "mb-3 rounded border" +
        (week.blank ? " border-danger" : " border-primary")
        }>

        <div className={"p-1" + (week.blank ? " bg-danger bg-opacity-25" : ' bg-success bg-opacity-10')}>
            <span className="fw-bold fs-4 me-2">{getWeekName(today, week.weekStart)}</span>
            <CheckButton variant="warning" checked={week.away}
                onChange={(away) => {
                    week.away = away;
                    week.blank = false;
                    forceUpdate();
                    onChange();
                }} text="Away?" className="text-dark"/>
        </div>

        { week.away ? null :
            <Row className="g-0" sm={4} md={7}>
            { week.avlDays.map((day, di) => <AvlDay key={di} week={week} day={day} onChange={onChange} />) }
            </Row>
        }
    </div>;
}

const RiderAvailabilityForm = ({ today, avlWeeks, onChange }) => <div className="ps-1 pe-1">
    {avlWeeks.map((week, wi) => <AvlWeek key={wi} today={today} week={week} onChange={onChange}>

    </AvlWeek>)}
</div>;

const RiderAvailabilityEditor = ({ initialDate }) => {
    const [data, {startDate}, dataSaved, isLoading, dataError, hasLock, save, reload, onEdit] = useEditableAjaxData(
        window.jsvars.data_url,
        window.jsvars.lock_url,
        1200,
        (data, {startDate}) => {
            return {
                date: startDate.valueOf(),
                weeks: data ? data.weeks : null,
            };
        },
        () => ({}),
        null,
        () => ({startDate: new Date(initialDate)})
    );

    const header = <span className="fs-1 me-2">My Shift Availability</span>;
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
        <div>
            {header}
            { dataSaved ? <Badge bg="success" className="fs-3 me-2">Saved</Badge> : <Badge bg="secondary" className="fs-3 me-2">Saving...</Badge> }
            { hasLock ? null : <Badge bg="warning" className="fs-5">Open somewhere else: close or reload this tab!</Badge>}
        </div>
        <p key={1} className="fw-bold">Select which shifts you are available to work.</p>
        <p key={2}>Select <b>Away</b> if you are away and add any rostering notes in the textbox under each tour's shifts.</p>

        { data.weeks.length == 0 ? <Alert variant="primary">No upcoming shifts.</Alert> : <>
        <RiderAvailabilityForm 
            today={startDate}
            avlWeeks={data.weeks}
            onChange={onEdit}
        />
        </> }
    </>;
};


module.exports = {RiderAvailabilityEditor};