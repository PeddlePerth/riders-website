const { Card, Row, Col, Table } = require('react-bootstrap');
const EditableTextField = require('./EditableTextField.js');

function TabularConfigRow({ fields, title, hint, rowData, onChange }) {
    return <tr>
        { title ? <th scope="row">
            <div key={0}>{ title }</div>
            { hint ? <div key={1} className="hints">{ hint }</div> : null }
            </th> : null }
        { fields.map((f, index) => <td key={index}>
            <EditableTextField 
                type={f.type}
                model={rowData}
                fieldName={f.field}
                isEditing={true}
                onChange={() => onChange()}
            />
        </td>
        )}
    </tr>;
}

function TabularConfigWidget({ title, rowTitleHeading, colHeadings, children }) {
    return <Card className="TabularConfigWidget border border-secondary">
        <Card.Header border="primary">{title}</Card.Header>
        <Table className="m-0">
            <thead>
                <tr>
                    { rowTitleHeading ? <th key={-1} scope="col">{ rowTitleHeading }</th> : null }
                    { colHeadings ? colHeadings.map((c, index) => <th key={index} scope="col">{c}</th>) : null }
                </tr>
            </thead>
            <tbody>
                { children }
            </tbody>
        </Table>
    </Card>;
}

const tour_type_fields = [
    { type: 'mins', label: 'Tour Pay Time', field: 'paid_duration_mins' },
    { type: 'money_short', label: 'Tour Pay Rate', field: 'pay_rate' },
];

const tour_role_fields = [
    { type: 'money_short', label: 'Role Pay Rate', field: 'pay_rate' },
];

const general_fields = [
    { type: 'mins', label: 'Max. Daily Paid Break', field: 'max_total_break_mins', hint: "Don't pay riders for more than this amount of break time per day"},
    { type: 'mins', label: 'Daily Unpaid Break', field: 'daily_unpaid_break_mins', hint: "Subtract this from the total paid break time per day" },
    //{ type: 'mins', label: 'Default Paid Break Time', field: 'default_paid_break_mins' },
    { type: 'mins', label: 'Time Before Unpaid Break', field: 'time_before_unpaid_break', hint: "Unpaid breaks are only allowed after a certain shift length" },
    { type: 'mins', label: 'Off-peak Minimum Paid Time', field: 'min_daily_mins', hint: "Add extra paid time for short shifts (Sun-Thurs only)" },
    { type: 'money_short', label: 'Default Pay Rate', field: 'default_rate'},
    { type: 'money_short', label: 'Break Pay Rate', field: 'break_pay_rate', hint: "Sets paid break rate (0 = use preceding tour pay rate)"},
    { type: 'mins', label: 'Pay all breaks under time', field: 'paid_break_max_len', hint: "All breaks under a certain time are paid breaks. Other settings for paid/unpaid breaks are ignored."},
];

function TourPayConfigurator({ payConfig, showOnlyTourTypes, onChange }) {
    var tourTypes = Object.entries(payConfig.tour_types);
    if (showOnlyTourTypes) {
        tourTypes = tourTypes.filter(([tour_type, pay]) => showOnlyTourTypes.includes(tour_type));
    }
    return <div className="TourPayConfigurator my-2">
        <h4>Pay Configuration</h4>
        <div className="m-1">
            <p className="hints">Hint: To fully redo pays after changing the config, save and then hit Reset Pays.</p>
            <p className="hints">
                Hint: Fixed rider pay rate rates always take precedence. The tour rate applies unless the rider role sets a different rate.
            </p>
            <p className="hints">Note: Changes to the pay config here will apply to all other past/future tour pay reports as well.</p>
        </div>
        <Row className="g-2">
            <Col key={1}>
            <TabularConfigWidget
                title="General Options"
                >
                { general_fields.map((f, i) => <TabularConfigRow
                    key={i}
                    title={f.label}
                    fields={[f]}
                    hint={f.hint}
                    rowData={payConfig}
                    onChange={onChange}
                />) }
            </TabularConfigWidget>
            </Col>
            <Col key={2}>
            <TabularConfigWidget
                title="Tour-specific Pay Rates" 
                colHeadings={tour_type_fields.map(f => f.label)}
                rowTitleHeading="Tour Type">
                { tourTypes.map(([tour_type, tt], index) => (
                    <TabularConfigRow key={index}
                        rowData={tt}
                        fields={tour_type_fields}
                        onChange={onChange}
                        title={tour_type}
                        titleWidth={4}
                    />
                )
            )}
            </TabularConfigWidget>
            </Col>
            <Col key={3}>
                <TabularConfigWidget
                    title="Role-specific Pay Rates"
                    colHeadings={tour_role_fields.map(f => f.label)}
                    rowTitleHeading="Rider Role">
                    { Object.entries(payConfig.roles).map(([role_id, role], index) => (
                        <TabularConfigRow key={index}
                            rowData={role}
                            fields={tour_role_fields}
                            onChange={onChange}
                            title={role.title}
                            titleWidth={6}
                        />
                    ))}
                </TabularConfigWidget>
            </Col>
        </Row>
    </div>;
}

module.exports = TourPayConfigurator;