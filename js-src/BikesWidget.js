const { createElement, Component } = require('react');
const { Stack, Badge } = require('react-bootstrap');
const FormattedInput = require('./FormattedInput');
const { plural } = require('./utils');

function compare_bikes(a, b) {
    a = a || {};
    b = b || {};

    let types = Object.keys(a).concat(Object.keys(b));
    for (var t of types) {
        if (a[t] != b[t]) return false;
    }
    return true;
}

function getPlural(name, num) {
    num = num || 0;
    if (num == 1) return name;
    return name + (name.endsWith('s') ? '' : 's');
}

function count_bikes(bikes) {
    if (!bikes) return 0;
    return Object.values(bikes).reduce((num, bikes) => num + (bikes || 0), 0);
}

function join_bikes(bikes) {
    return bikes.reduce((res, next) => {
        Object.keys(next).forEach(bikeId => (res[bikeId] = (res[bikeId] || 0) + (next[bikeId] || 0)));
        return res;
    }, {});
}

function describe_bikes(bikes, bikeTypes) {
    const numBikes = count_bikes(bikes);
    const extras = Object.keys(bikes)
        .filter(bt => (bt !== 'bike' && bikeTypes[bt] && bikeTypes[bt].quantity > 0))
        .map(bt => (bikeTypes[bt].quantity == 1 ? bikeTypes[bt].name : `${bikes[bt]} ${getPlural(bikeTypes[bt].name, bikes[bt])}`))
        .join(' & ');
    const bikeStr = `${numBikes} ${getPlural('bike', numBikes)}`;
    if (extras) return bikeStr + ' including ' + extras;
    return bikeStr;
}

function TSRiderInfo({ tour }) {
    const numBikes = count_bikes(tour.bikes);
    const numRiders = tour.riders.length;

    var ridersBadge = null;
    if (numRiders < numBikes) {
        let needed = numBikes - numRiders;
        ridersBadge = <Badge bg='danger' key={tour.id} className="me-1 text-wrap">{plural(needed, ' RIDER', ' RIDERS') + ' NEEDED'}</Badge>;
    } else if (numRiders > numBikes) {
        ridersBadge = <Badge bg='warning' key={tour.id} className="me-1 text-wrap">TOO MANY RIDERS</Badge>;
    }
    return ridersBadge;
}

function TSBikesInfo({ tour, bikeTypes, className }) {
    const specificBikes = Object.keys(tour.bikes)
        .filter(bt => (bikeTypes[bt] && bikeTypes[bt].quantity > 0))
        .map(bt => 
            <Badge key={bt} bg="info" className="me-1 text-wrap">
                { 
                bikeTypes[bt].quantity == 1 ? 
                    ('Needs ' + bikeTypes[bt].name) : 
                    (tour.bikes[bt] + ' ' + getPlural(bikeTypes[bt].name, tour.bikes[bt]))
                }
            </Badge>
        );
    
    return <div className={"BikesInfo" + (className ? ' ' + className : '')}>
        { specificBikes }
    </div>;
}

class BikesWidget extends Component {
    constructor(props) {
        super(props);

        this.onChange = this.onChange.bind(this);
    }

    onChange(bike_id, val) {
        const bikes = this.props.model[this.props.fieldName];
        if (val > this.props.bikeTypes[bike_id].quantity)
            val = this.props.bikeTypes[bike_id].quantity;
        if (val < 1) {
            delete bikes[bike_id];
        } else {
            bikes[bike_id] = val;
        }

        if (this.props.onChange) this.props.onChange(bikes);
    }

    render() {
        const bikes = this.props.model[this.props.fieldName];
        let auto_values = this.props.model.field_auto_values;


        const isCurrent = auto_values ? compare_bikes(bikes, auto_values[this.props.fieldName]) : true;
        return createElement(Stack, {
                direction: 'vertical',
                className: 'BikesWidget' + (isCurrent ? ' Current' : ' Changed') + (this.props.className ? ' ' + this.props.className : ''),
            },
            Object.entries(this.props.bikeTypes).filter(([id, bike]) => bike.quantity > 0).map(([id, bike], index) => 
            createElement(FormattedInput, {
                    key: index,
                    type: 'positiveint',
                    value: bikes[id],
                    label: getPlural(bike.name),
                    isEditing: true,
                    onChange: (val) => this.onChange(id, val),
                }),
            ));
    }
}

BikesWidget.defaultProps = {
    onChange: () => null,
    model: {},
    fieldName: 'bikes',
};

module.exports = { BikesWidget, describe_bikes, compare_bikes, count_bikes, join_bikes, TSBikesInfo, TSRiderInfo };