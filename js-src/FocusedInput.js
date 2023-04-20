// Input element which responds to keyboard and focus events
const { createElement, Component } = require('react');
const FormattedInput = require('./FormattedInput');
const { setCursor } = require('./utils');

class FocusedInput extends Component {
    constructor(props) {
        super(props);

        this.state = {
            elId: Math.floor(Math.random() * 10000000000).toString(),
        };

        this.onBlur = this.onBlur.bind(this);
        this.onKeyDown = this.onKeyDown.bind(this);
        this.onInputSubmit = this.onInputSubmit.bind(this);
        this.onChange = this.onChange.bind(this);
        this.onInputRef = this.onInputRef.bind(this);
        this.inputEl = null;
    }

    // called when the textbox loses focus (including when result click event is fired)
    onBlur() {
        // try to find the selected item from the textbox text
        if (this.props.onCommit) this.props.onCommit(false);
    }

    onChange(val) {
        if (this.props.onChange) this.props.onChange(val);
    }

    onKeyDown(event) {
        if (event.key == 'Tab') { // TAB key pressed
            event.preventDefault();
            if (this.props.onCommit) this.props.onCommit(true);
        }
    }

    doFocus() {
        if (this.inputEl && this.inputEl !== document.activeElement) {
            this.inputEl.focus();
            if (this.props.cursorPos !== null) {
                try {
                    setCursor(this.inputEl, this.props.cursorPos);
                } catch (e) {
                    //console.log(e);
                }
            }
        }
    }

    componentDidMount() {
        this.doFocus();
    }

    componentDidUpdate() {
        this.doFocus();
    }

    onInputSubmit(event) {
        event.preventDefault();
        if (this.props.onCommit) this.props.onCommit(true);
    }

    onInputRef(el) {
        this.inputEl = el;
        if (this.props.inputRef) this.props.inputRef(el);
    }

    render() {
        // use a form to trap "Enter" key press
        return createElement('form', {
                autoComplete: 'off',
                style: this.props.style,
                className: 'FocusedInput' + (this.props.className ? ' ' + this.props.className : '') + 
                    (this.props.isEditing ? ' Editing' : ''),
                onSubmit: this.onInputSubmit,
                onClick: this.props.onClick,
            },
            createElement(FormattedInput, {
                type: this.props.type,
                name: this.state.elId, 
                id: this.state.elId,
                value: this.props.value,
                isEditing: this.props.isEditing,
                indexChars: this.props.indexChars,
                onBlur: this.onBlur,
                onChange: this.onChange,
                onKeyDown: this.onKeyDown,
                inputRef: this.onInputRef,
                style: this.props.style,
            }),
            this.props.extraElements,
        );
    }
}

FocusedInput.defaultProps = {
    inputRef: (el) => null,
    cursorPos: null,
    indexChars: false,
};

module.exports = FocusedInput;