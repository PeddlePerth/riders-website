const { useState } = require('react');
const { Stack } = require('react-bootstrap');
const { AutocompleteTextBoxV2 } = require('./AutocompleteTextBox.js');

function TourRidersWidget({ canAddRider, onAddRider, allRiders, children }) {
    const [editing, setEditing] = useState(false);

    return <Stack 
        direction="vertical" 
        gap={1} 
        className="TourRidersWidget"
        onClick={(e) => {
            setEditing(true);
            e.preventDefault();
        }}
        >
        { children }
        { editing ? <AutocompleteTextBoxV2 
            onSelect={(item) => {
                if (item && canAddRider(item.id)) {
                    onAddRider(item.id);
                }
                return true; // clear ACB selection after adding rider
            }}
            onBlur={() => setEditing(false)}
            items={Object.keys(allRiders).map(id => allRiders[id])}
        /> : null }
    </Stack>;
}

module.exports = TourRidersWidget;