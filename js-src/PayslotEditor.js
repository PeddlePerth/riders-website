const { createElement, Component } = require('react');
const { ListGroup, Row, Col, Stack, Button } = require('react-bootstrap');
const { format_time_12h } = require('./utils.js');
const FormattedInput = require('./FormattedInput.js');
const EditableTextField = require('./EditableTextField.js');

const PAYSLOT_FIELDS = {
    //time_start: { fieldName: 'time_start', type: 'time', label: 'Start Time' },
    //time_end: { fieldName: 'time_end', type: 'time', label: 'End Time' },
    pay_minutes: { fieldName: 'pay_minutes', type: 'mins', label: 'Pay Mins' },
    pay_rate: { fieldName: 'pay_rate', type: 'money_short', label: 'Pay Rate' },
    pay_reason: { fieldName: 'pay_reason', type: 'text', label: 'Pay Reason' },
    description: { fieldName: 'description', type: 'text', label: 'Description' },
};

class PayslotEditor extends Component {
    constructor(props) {
        super(props);

        // create ref objects for all the fields
        this.state = {
            fieldRefs: Object.fromEntries(
                Object.values(PAYSLOT_FIELDS).map(field => [field.fieldName, React.createRef()])),
        };
    }

    getField(name, className) {
        return createElement(EditableTextField, {
            ...PAYSLOT_FIELDS[name],
            model: this.props.payslot,
            key: name,
            className: className,
            onCommit: () => this.props.onChange(),
        });
    }

    render() {
        const payslot = this.props.payslot;
    
        return createElement(ListGroup.Item, { className: 'RiderPaySlot ps-' + payslot.slot_type }, 
            createElement(Row, {},
                createElement(Col, { className: 'rider-tour-info', xs: 9 }, 
                    createElement('div', { className: 'rider-tour-times' }, 
                        `${format_time_12h(payslot.time_start)}\u2012${format_time_12h(payslot.time_end)} `),
                    this.getField('description', 'rider-tour-type'),
                    this.getField('pay_reason', 'rider-tour-type'),
                ),
                createElement(Col, { className: 'rider-tour-pay-info', xs: 3 },
                    createElement(Stack, { direction: 'vertical' },
                        this.getField('pay_minutes', 'rider-tour-hours'),
                        this.getField('pay_rate', 'rider-tour-pay-rate'),
                        createElement(FormattedInput, {
                            className: 'rider-tour-pay',
                            type: 'money',
                            value: payslot.pay_rate * (payslot.pay_minutes / 60),
                        }),
                    ),
                ),
            )
        );
    }
}

module.exports = PayslotEditor;