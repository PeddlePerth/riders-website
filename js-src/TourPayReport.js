const { createElement, Component } = require('react');
const { Table, Row, Col, Card, ListGroup, Button, Stack, Container } = require('react-bootstrap');
const PayslotEditor = require('./PayslotEditor.js');
const FormattedInput = require('./FormattedInput.js');
const TourPayConfigurator = require('./TourPayConfigurator.js');
const { downloadFile, formatCSV, format_iso_date, format_num } = require('./utils.js');

function daySubtotal(pay_day) {
    return pay_day.reduce((cumulative, payslot) => cumulative + (payslot.pay_rate * (payslot.pay_minutes / 60)), 0);
}

function dayHoursTotal(pay_day) {
    return pay_day.reduce((hh, payslot) => hh + (payslot.pay_minutes / 60), 0);
}

function riderSubtotal(rider_pay_days) {
    return Object.values(rider_pay_days).reduce((cumulative, pay_day) => cumulative + daySubtotal(pay_day), 0);
}

function EmptyRiderTourDay(props) {
    return createElement(Col, { });
}

class RiderTourDay extends Component {
    constructor(props) {
        super(props);

        /*this.state = {
            subTotal: daySubtotal(this.props.payslots),
            totalHours: dayHoursTotal(this.props.payslots),
        };*/

        this.onPayslotChanged = this.onPayslotChanged.bind(this);
    }

    onPayslotChanged(payslotId, payslot) {
        // Perform minimal state updates/recalculations when a payslot is changed
        //console.log('RiderTourDay payslot changed', payslotId, payslot);
        this.props.onPayslotChanged(payslotId, payslot, false);
        /*this.setState({
            subTotal: daySubtotal(this.props.payslots),
            totalHours: dayHoursTotal(this.props.payslots),
        });*/
    }

    // TODO: onPayslotAdded

    render() {
        const subTotal = daySubtotal(this.props.payslots), totalHours = dayHoursTotal(this.props.payslots);

        return createElement(Col, { }, createElement(Card, { className: 'RiderTourDay' },
            createElement(Card.Header, { },
                createElement(Stack, { direction: 'horizontal', className: 'Header' }, 
                    <>
                        <span className="fw-bold">{ this.props.date }</span>&mdash;
                        <span className="text-highlight">${ format_num(subTotal, 0, 2, 2) }</span>
                        <span>&nbsp;({ format_num(totalHours, 1, 0, 2) }h)</span>
                    </>
                )
            ),
            createElement(ListGroup, { variant: 'flush' },
                this.props.payslots
                    .sort((a, b) => a.time_start - b.time_start)
                    .map(
                    payslot =>
                        createElement(PayslotEditor, {
                            // yay for prop drilling!
                            payslot: payslot,
                            key: payslot.id,
                            onChange: this.onPayslotChanged,
                        })
                ),
            ),
        ));
    }
}

function RiderTourRow({ rider, children }) {
    return <Row className="rider-tours-row g-0">
        <Col xs={1} className="rider-tours-name" key={1}>
            <div key={1}>{ rider.title }</div>
            <div className="hints" key={3}>{ rider.name }</div>
            { rider.pay_rate ? <div className="hints" key={2}>Fixed rate: ${rider.pay_rate.toFixed(2)}</div> : null }
        </Col>
        <Col xs={10} key={2}>
            <Row className="g-0 rider-tours-tours">{ children }</Row>
        </Col>
        <Col xs={1}>
            <span className="rider-tour-pay">
            ${(riderSubtotal(rider.pay_days) ?? 0).toFixed(2)}
            </span>
        </Col>
    </Row>;
}

class TourPayReportV2 extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            showConfig: false,
        };

        this.state.riderList = Object.entries(this.props.riders).sort(([id1, r1], [id2, r2]) => r1.name > r2.name).map(([id, r]) => id);
        /*this.state.riderSubtotals = Object.fromEntries(this.state.riderList.map(
            riderId => [riderId, riderSubtotal(this.props.riders[riderId].pay_days)]
        ));*/

        this.onPayslotChanged = this.onPayslotChanged.bind(this);
        this.exportCSV = this.exportCSV.bind(this);
    }

    onPayslotChanged(payslotId, payslot, isNew) {
        console.log('Updated payslot', payslotId, payslot);
        if (isNew) throw "BLAAAAAH no new payslots supported";
        this.props.onEdit();
    }

    exportCSV() {
        var rows = [['Rider Name', 'Pay', 'BSB', 'Account Number']];
        rows = rows.concat(this.state.riderList.map(rider_id => {
            const riderPay = this.props.riders[rider_id];
            return [
                riderPay.name,
                '$' + (riderSubtotal(riderPay.pay_days) ?? 0).toFixed(2),
                riderPay.bsb,
                riderPay.acct,
            ];
        }));
        const filename = `TourPays_${format_iso_date(this.props.start_date)}_${format_iso_date(this.props.end_date)}.csv`;
        console.log(filename, rows);
        downloadFile(filename, formatCSV(rows), 'text/csv');
    }

    render() {
        return <div className='TourPayReport'>
            <Stack direction='horizontal' className='Toolbar m-1'>
                <Button variant='primary' className='mx-1' key={1}
                    onClick={ () => this.setState({ showConfig: !this.state.showConfig })}>
                        <span className="bi-gear-fill"></span>
                        { this.state.showConfig ? ' Hide Pay Config' : ' Show Pay Config' }
                </Button>
                <Button variant="danger" className="mx-1" key={2}
                    onClick={ () => this.props.onAction('reset') }>
                    Reset Pays
                </Button>
                <Button variant="secondary" className="mx-1" key={3}
                    onClick={this.exportCSV}>
                    Export CSV
                </Button>
                { this.props.ajaxToolbar }
            </Stack>
            {
                this.state.showConfig ? <TourPayConfigurator
                    payConfig={this.props.tour_pay_config}
                    showOnlyTourTypes={this.props.tour_types_seen}
                    onChange={ () => this.props.onEdit() }
                /> : null
            }
            <Row className="header g-0">
                <Col xs={1} key={1}>Rider</Col>
                <Col xs={10} key={2} className="rider-tour-day">Tours &amp; Pay Breakdown</Col>
                <Col xs={1} key={3}>Rider Subtotal</Col>
            </Row>
            {
                this.state.riderList.map(rider_id => this.props.riders[rider_id]).map(riderPay =>
                    createElement(RiderTourRow, {
                            key: riderPay.id,
                            rider: riderPay,
                        },
                        this.props.days.map(([isodate, date, daystr]) => 
                        (isodate in riderPay.pay_days) ? createElement(RiderTourDay, {
                                key: isodate,
                                date: daystr,
                                riderId: riderPay.id,
                                payslots: riderPay.pay_days[isodate],
                                onPayslotChanged: this.onPayslotChanged,
                            }) : createElement(EmptyRiderTourDay, { key: isodate }))
                    ))
            }
        </div>;

    }
}

module.exports = TourPayReportV2;