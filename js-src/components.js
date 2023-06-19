const { createElement, Component, useState } = require('react');
const { ButtonGroup, Stack, Button, ToggleButton } = require('react-bootstrap');

class MyButtonGroup extends Component {
    constructor(props) {
        super(props);

        this.onBtnClick = this.onBtnClick.bind(this);
    }

    onBtnClick(event, item) {
        this.props.onBtnClick(item.id);
        event.preventDefault();
    }

    render() {
        return createElement(ButtonGroup, { 
            size: 'sm',
            className: this.props.className,
        }, this.props.items.map(item => createElement(Button, {
                variant: item.variant,
                active: this.props.value == item.id,
                className: item.icon ? item.icon : '',
                onClick: event => this.onBtnClick(event, item),
                key: item.id,
            }, item.title)),
        );
    }
}

function TextLabel(props) {
    return createElement('div', { className: 'text-label' },
        createElement('span', { className: 'label-title' }, props.title),
        ' ',
        createElement('span', { className: 'label-text' }, props.text),
        props.children,
    );
}

function ToggleCell(props) {
    return createElement('td', {
        onClick: event => props.onChange(!props.value),
        className: 'ToggleCell' + (props.value ? ' active' : ''),
    });
}

function LabelInput(props) {
    return createElement(Stack, { direction: 'horizontal', className: props.className }, 
        createElement('span', { className: 'label-for-input' }, props.title),
        createElement('input', { 
            type: props.type,
            onChange: (event) => {
                if (props.type == 'number') props.onChange(parseInt(event.target.value));
                else if (props.type == 'checkbox') props.onChange(!props.value);
                else props.onChange(event.target.value);
            },
            value: props.value,
            checked: props.checked,
        }),
    );
}

var nextId = 0;
function CheckButton({ checked, text, variant="success", size, className, onChange }) {
    const [chkId, setChkId] = useState(++nextId);
    return <ToggleButton
        className={className}
        type="checkbox"
        id={"chkb" + chkId}
        variant={checked ? variant : ("outline-" + variant)}
        checked={checked}
        size={size}
        onChange={(e) => {
            if (onChange) onChange(e.currentTarget.checked)
        }}
        >
            { checked ? <span className="bi-check-square-fill"></span> : <span className="bi-square"></span> }
            <span key={2} className="ms-2">{ text }</span>
        </ToggleButton>;
}

module.exports = {
    MyButtonGroup,
    TextLabel,
    ToggleCell,
    LabelInput,
    CheckButton,
}