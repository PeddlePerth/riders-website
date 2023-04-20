const { format_num, htmlLines } = require('./utils.js');
const { createElement, Component } = require('react');
const { Stack } = require('react-bootstrap');
const $ = require('jquery');
const { autoGrowInput, autoHeightTd } = require('./utils.js');

function parseNum(val, min, max) {
    min = min || Number.MIN_SAFE_INTEGER;
    max = max || Number.MAX_SAFE_INTEGER;
    val = parseInt(val);
    if (isNaN(val) || val === Infinity || val === undefined) return null;
    if (val > max) return max;
    if (val < min) return min;
    return val;
}

function telephone(number) {
    return createElement('a', { className: 'telephone', href: 'tel:' + number }, number);
}

function underline(text) {
    return createElement('u', { }, text);
}



// fromRawValue: translate raw value (string from input element) into actual value (with correct data type)
// toRawValue: translate from actual value into raw value for input element
// displayValue: translate from raw value into whatever React nodes are displayed when not editing
const VALUE_TYPES = {
    money: { prefix: '$', toRawValue: (val) => format_num(val, 0, 2, 2), fromRawValue: (val) => parseNum(val, 0), inputType: 'number' },
    hours: { suffix: 'h', toRawValue: (val) => format_num(val, 1, 0, 2), fromRawValue: (val) => parseNum(val, 0), inputType: 'number' },
    mins: { suffix: 'm', toRawValue: (val) => format_num(val, 0, 0, 0), fromRawValue: (val) => parseNum(val, 0), inputType: 'number' },
    money_short: { prefix: '$', toRawValue: (val) => format_num(val, 1, 0, 2), fromRawValue: (val) => parseNum(val, 0), inputType: 'number'},
    positiveint: { toRawValue: (val) => format_num(val, 0, 0, 0), fromRawValue: (val) => parseNum(val, 0), inputType: 'number' },
    text: { inputType: 'text' },
    name: { inputTag: 'textarea', displayValue: underline },
    phone: { inputType: 'text', displayValue: telephone },
    textarea: { inputTag: 'textarea' },
};

// input with some labels on either side, value formats, and automatic resizing for input
class FormattedInput extends Component {
    constructor(props) {
        super(props);
        this.inputRef = this.inputRef.bind(this);
        this.onChange = this.onChange.bind(this);
        this.containerRef = this.containerRef.bind(this);
        
        this.inputEl = null;
        this.inputSizeUnbind = null;
    }

    containerRef(el) {
        if (el !== null && this.props.autoHeightTd) {
            autoHeightTd(el);
        }
    }

    inputRef(el) {
        const { inputTag, inputType } = VALUE_TYPES[this.props.type];
        
        // manage automatic sizing
        if (inputTag !== 'textarea') {
            if (el !== null && this.inputEl === null) {
                this.inputSizeUnbind = autoGrowInput(el, inputType === 'number' ? {
                    minWidth: 40,
                    comfortZone: 40,
                } : {}); // setup the bindings
            } else if (el === null && this.inputSizeUnbind !== null) {
                this.inputSizeUnbind();
            }
        }
        this.inputEl = el;
        if (this.props.inputRef) this.props.inputRef(el);
    }

    onChange(event) {
        // translate the value in the component (raw value) to the correct type (actual value)
        // and this should also translate back to the same raw value when formatted
        const val = event.target.value;
        const { fromRawValue } = VALUE_TYPES[this.props.type];

        if (this.props.onChange) {
            this.props.onChange(fromRawValue ? fromRawValue(val) : val);
        }
    }

    getCharacterBits(text) {
        const els = [];
        for (var i = 0; i < text.length; i++) {
            let char = text[i];
            if (char == '\n') {
                els.push(createElement('br', { key: i }));
            } else {
                els.push(createElement('span', {
                    key: i,
                    charindex: i,
                }, char));
            }
        }
        return els;
    }

    render() {
        const props = this.props;
        const { prefix, suffix, toRawValue, displayValue, inputType, inputTag } = VALUE_TYPES[props.type];
        const val = toRawValue ? toRawValue(props.value) : props.value;

        var input;
        if (props.isEditing) {
            const inputProps = {
                className: 'Value',
                onChange: this.onChange,
                onBlur: props.onBlur,
                onKeyDown: props.onKeyDown,
                value: val,
                id: props.id,
                name: props.name,
                type: inputType,
                ref: this.inputRef,
                tabIndex: props.tabIndex,
                style: props.style,
            };
            
            input = (inputTag == 'textarea' ? createElement('textarea', inputProps) : createElement('input', inputProps))
        } else {
            let chars = this.props.indexChars ? this.getCharacterBits(val) : htmlLines((val || '').trim());
            input = createElement('span', { className: 'Value' },
                displayValue ? displayValue(chars) : chars
            );
        }

        return createElement('div', {
                className: "FormattedInput" + (props.className ? " " + props.className : "") + 
                    (props.isEditing ? ' Editing' : ''),
                onClick: props.onClick,
                ref: this.containerRef,
            }, 
            props.label ? createElement('span', { className: 'Label' }, props.label, ' ') : null,
            prefix ? createElement('span', { className: 'Prefix' }, prefix) : null,
            input,
            suffix ? createElement('span', { className: 'Suffix' }, suffix) : null,
        );
    }
}

FormattedInput.VALUE_TYPES = VALUE_TYPES;

FormattedInput.defaultProps = {
    autoHeightTd: false,
    indexChars: false,
};

module.exports = FormattedInput;