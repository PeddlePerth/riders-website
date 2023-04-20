const { createElement, Component } = require('react');
const { Stack, Badge, Button, Spinner } = require('react-bootstrap');
const { post_data } = require('./utils.js');

class AjaxDataComponent extends Component {
    constructor(props) {
        super(props);

        this.state = {
            lastSave: null,
            data: null,
            lastUpdate: null,
            lastEdit: null,
            errorMsg: null,
        };

        this.onEdit = this.onEdit.bind(this);
        this.onSave = this.onSave.bind(this);
        this.onAction = this.onAction.bind(this);
        this.onDataLoaded = this.onDataLoaded.bind(this);
        this.beforeUnload = this.beforeUnload.bind(this);
    }

    onEdit() {
        this.setState({ lastEdit: new Date() });
    }

    onAction(verb, mustSave) {
        // Send the action to the server and get the result
        if (mustSave) this.onSave(verb);
        else {
            const postData = {
                ...this.props.extraPostData,
                action: verb,
            };
            post_data(this.props.postUrl, postData, this.onDataLoaded);
        }
    }

    onSave(verb, onComplete) {
        // Save the data to the server
        const postData = {
            ...this.props.extraPostData,
            ...this.props.getPostData(this.state.data),
            action: verb,
        };
        post_data(this.props.postUrl, postData, (ok, response) => {
            this.onDataLoaded(ok, response); 
            if (onComplete) onComplete(ok);
        });
    }

    // Retrieve updated data & reload component
    onDataLoaded(ok, response) {
        //console.log("got data:", ok, response);
        if (!ok) {
            this.setState({ errorMsg: response });
            return;
        } else {
            this.setState({ errorMsg: null, lastSave: new Date() });
        }

        // wholesale import/update data
        if (response) {
            this.setState({ data: response, lastUpdate: new Date() });
            this.props.dataRef(response);
        }
    }

    isSaved() {
        return (this.state.lastSave !== null && this.state.lastEdit !== null && this.state.lastSave >= this.state.lastEdit)
            || this.state.lastEdit === null;
    }

    isLoaded() {
        return this.state.lastUpdate !== null;
    }

    beforeUnload() {
        if (!this.isSaved()) return "There is unsaved data on the page! Are you sure you want to leave?";
    }

    componentDidMount() {
        window.onbeforeunload = this.beforeUnload;
        post_data(this.props.postUrl, this.props.extraPostData, this.onDataLoaded);
        console.log("loading Ajax data from " + this.props.postUrl);
    }

    componentWillUnmount() {
        if (window.onbeforeunload === this.beforeUnload) window.onbeforeunload = null;
    }

    render() {
        const saveStatus = !this.isLoaded() ? 'Loading...' :
            (this.isSaved() ? (this.state.lastSave ? 
            `Last save: ${this.state.lastSave.toLocaleTimeString()}` : 'No changes')
            : `Last edit: ${this.state.lastEdit.toLocaleTimeString()}`);
        const toolbarItems = [
            createElement(Button, {
                className: 'SaveBtn mx-1',
                variant: this.isSaved() ? 'secondary' : 'success',
                onClick: () => this.onSave(),
                key: 'save',
            }, 'Save'),
            this.props.extraToolbar,
            createElement(Badge, { className: 'mx-1', bg: 'info', key: 'badge', }, saveStatus),
            this.state.errorMsg ? createElement(Badge, { bg: 'danger', key: 'badge2', }, this.state.errorMsg) : null,
        ];
        return createElement(Stack, { direction: 'vertical', className: 'AjaxDataComponent' },
            this.props.extraHeader,
            this.isLoaded() ? 
                createElement(this.props.dataConsumer, {
                    ...this.props.dataConsumerProps,
                    ...this.state.data,
                    onAction: this.onAction,
                    onEdit: this.onEdit,
                    onSave: this.onSave,
                    ajaxToolbar: toolbarItems,
                }) : <div className="text-center p-2"><Spinner animation="border"/></div>,
        );
    }
}

AjaxDataComponent.defaultProps = {
    extraToolbar: null,
    extraHeader: null,
    dataConsumer: null,
    data: null,
    dataConsumerProps: {},
    extraPostData: {},
    postUrl: null,
    dataRef: (data) => null,
    getPostData: (data) => data,
};

module.exports = AjaxDataComponent;