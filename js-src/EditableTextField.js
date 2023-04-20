const { createElement, Component } = require('react');
const { Stack } = require('react-bootstrap');
const $ = require('jquery');
const FocusedInput = require('./FocusedInput.js');
const FormattedInput = require('./FormattedInput.js');

// TODO: click-to-edit thing which updates an "model" instance's fields directly
class EditableTextField extends Component {
    constructor(props) {
        super(props);

        this.state = {
            showAutoVal: false, // show the auto value if it is different from the actual value
            editing: this.props.isEditing,
            initialCursorPos: 0,
            initialHeight: null,
        };

        this.onChange = this.onChange.bind(this);
        this.onCommit = this.onCommit.bind(this);
        this.onClick = this.onClick.bind(this);
        this.containerEl = null;
    }

    getMetadata() {
        // Ensure the model object has everything we need
        // Don't copy anything out of the object, only use references
        // Avoid creating unbound "children" of the object, make sure to assign them to the original object somewhere
        const obj = this.props.model;
        const field = this.props.fieldName;

        const actual_value = obj[field];
        const field_auto_values = obj.field_auto_values || {};
        const auto_value = field_auto_values[field] || actual_value;

        return [actual_value, auto_value];
    }

    onChange(val) {
        // This is a controlled component but we use the object instance itself to store
        // the latest value, rather than the state (sorry React)
        this.props.model[this.props.fieldName] = val;
        
        this.forceUpdate();

        if (this.props.onChange) {
            this.props.onChange(this.props.fieldName);
        }
    }

    onCommit(cancellable) {
        this.setState({ editing: false });
        if (this.props.onCommit)
            this.props.onCommit(this.props.fieldName);
    }

    onClick(event) {
        const [val, auto_val] = this.getMetadata();
        if (this.props.editable && !this.state.editing) {
            let cursorPos = 0, charIndex = event.target.attributes['charindex'];
            if (charIndex) {
                cursorPos = parseInt(charIndex.value);
            } else {
                cursorPos = ('' + val).length;
            }
            let height = this.containerEl ? $(this.containerEl).height() : null;

            this.setState({
                editing: true,
                initialCursorPos: cursorPos,
                initialHeight: height,
            });
        }
    }

    render() {
        const [val, auto_val] = this.getMetadata();

        const isCurrent = (val === auto_val);
        const style = { minHeight: (this.state.editing && this.state.initialHeight) ? `${this.state.initialHeight-2}px` : null };

        return <div
            className={'EditableTextField' + (this.props.className ? (" " + this.props.className) : "") +
                (isCurrent ? " Current" : " Changed") +
                (this.state.editing ? " Editing" : '')}
            ref={(el) => this.containerEl = el }
            style={style}
            >
            { createElement(FocusedInput, {
                type: this.props.type,
                label: this.props.label,
                value: val,
                onClick: this.onClick,
                onChange: this.onChange,
                onCommit: this.onCommit,
                indexChars: true,
                cursorPos: this.state.initialCursorPos,
                isEditing: this.state.editing,
                style: style,
            }) }
        </div>;
    }
}

EditableTextField.defaultProps = {
    model: {},
    fieldName: '',
    editable: true,
    tabIndex: undefined,
    isEditing: false,
    underline: false,
    onChange: (fieldName) => null,
    onCommit: (fieldName) => null,
};

module.exports = EditableTextField;