const { Badge, Row, Col, Button, ButtonGroup } = require('react-bootstrap');
const TourRidersWidget = require('./TourRidersWidget.js');
const EditableTextField = require('./EditableTextField.js');
const RiderWidget = require('./RiderWidget.js');
const { BikesWidget, TSBikesInfo, TSRiderInfo } = require('./BikesWidget.js');
const { TourVenuesEditorV2, makeVenues } = require('./TourVenuesEditor.js');
const { TSCancelledBadge } = require('./TourScheduleViewer.jsx');

const tour_fields = {
    customer_name: { type: 'name' },
    customer_contact: { type: 'textarea' },
    quantity: { type: 'textarea' },
    pickup_location: { type: 'textarea' },
    notes: { type: 'textarea' },
};

// create the row containing tour data
const TourRow = ({tour, allRiders, allVenues, bikeTypes, canAddRider, onAddRider, onDelRider, onChgRider, onEdit, onChgBikes, venuePresets}) => {
    function getField(fieldName) {
        const f = tour_fields[fieldName];
        return <EditableTextField
            type={f.type}
            fieldName={fieldName}
            model={tour}
            onCommit={onEdit}
        />;
    }

    return (
    <Row className="TourScheduleRow g-0">
        <Col key={1} xs={8}>
            <Row className="g-0">
                <Col key={1} xs={3}>
                    <TourRidersWidget
                        allRiders={allRiders}
                        canAddRider={rider_id => canAddRider(rider_id, tour.time_start, tour.time_end)}
                        onAddRider={rider_id => onAddRider(tour.id, rider_id)}>
                        {
                            tour.source_row_state == 'deleted' ? <TSCancelledBadge/> :
                            <>
                                <TSBikesInfo tour={tour} bikeTypes={bikeTypes} />
                                <div><TSRiderInfo tour={tour} /></div>
                            </>
                        }
                        { tour.riders.map((tour_rider, index) => 
                            <RiderWidget key={index}
                                {...allRiders[tour_rider.rider_id]}
                                roleSelected={tour_rider.rider_role}
                                tourId={tour.id}
                                onDelRider={rider_id => onDelRider(tour.id, rider_id)}
                                onRoleChanged={(rider_id, role) => onChgRider(tour.id, rider_id, role)}
                            />)}
                    </TourRidersWidget>
                </Col>
                <Col key={2} xs={3}>{ getField('customer_name') }</Col>
                <Col key={3} xs={2}>{ getField('customer_contact') }</Col>
                <Col key={4}>
                    <Row className="g-0 h-100" xs={1}>
                        <Col>{ getField('quantity', true) }</Col>
                        <Col>
                            <BikesWidget 
                                model={tour}
                                bikeTypes={bikeTypes}
                                onChange={(bikes) => onChgBikes(tour.id, bikes)}
                            />
                        </Col>
                    </Row>
                </Col>
                <Col key={5}>{ getField('pickup_location') }</Col>
            </Row>
        </Col>
        <Col key={2} xs={4} className="position-relative">
            { getField('notes') }
            <ButtonGroup className="venue-presets" size="sm">
                { window.jsvars.admin_url ? 
                <Button title="Edit on Admin Site" target="blank" href={window.jsvars.admin_url.replace('TOUR_ID', tour.id)} variant="secondary">
                    <span className="bi-pencil"/>
                </Button> : null }
                { Object.entries(venuePresets).map(([pname, preset], i) => (
                <Button key={i}
                    title="Add venues from preset"
                    onClick={() => {
                        tour.venues = makeVenues(tour.id, preset);
                        // force component update??
                        onEdit();
                    }}
                    >
                    <span className="bi-plus-lg" />&nbsp;{pname}
                </Button>))}
                { tour.venues.length > 0 ? <Button
                    variant="danger"
                    title="Clear Venues"
                    onClick={() => {
                        tour.venues = [];
                        onEdit();
                    }}>
                    <span className="bi-trash"></span>&nbsp;Venues
                </Button> : null }
            </ButtonGroup>
        </Col>
        { tour.venues.length > 0 ? 
        <Col key={3} xs={12} className="position-relative">
            <TourVenuesEditorV2 
                tour={tour}
                allVenues={allVenues}
                onChange={onEdit}
            />
        </Col> : null
        }
    </Row>
    );
}

module.exports = TourRow;