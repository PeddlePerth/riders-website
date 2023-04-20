const { createElement, Component } = require('react');
const { Stack } = require('react-bootstrap');
const { MyButtonGroup } = require('./components.js');

class RiderWidget extends Component {
    constructor(props) {
        super(props);

        this.btnClick = this.btnClick.bind(this);
    }

    btnClick(btn) {
        if (btn == 'delete') {
            this.props.onDelRider(this.props.id);
        } else {
            if (this.props.roleSelected == btn)
                this.props.onRoleChanged(this.props.id, null); // toggle role if already selected
            else this.props.onRoleChanged(this.props.id, btn);
        }
    }

    render() {
        const roleButtons = [{
            id: 'lead', title: 'L', variant: "outline-primary",
        }, {
            id: 'colead', title: 'CL', variant: "outline-secondary",
        }, {
            id: 'delegate', title: 'Del', variant: "outline-info",
        }, {
            id: 'delete', title: 'X', variant: 'danger',
        }];

        return <div className="RiderWidget d-flex flex-wrap">
            <span className="rider-name me-auto">{this.props.title}</span>
            <MyButtonGroup className="flex-align-end" onBtnClick={this.btnClick} value={this.props.roleSelected} items={roleButtons}/>
        </div>;
    }
}

module.exports = RiderWidget;