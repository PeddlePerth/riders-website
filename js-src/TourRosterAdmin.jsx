const { format_short_date } = require("./utils");

const TourRosterViewer = ({ toursDate, tourArea, rosters, errorRosters, onEdit, onSave, onAction, isLoaded, isSaved, saveStatus }) => {
    return <>
        <h2>Deputy Tour Shifts for { format_short_date(toursDate) }</h2>
        <span className="p-1 rounded-3 text-white" style={{backgroundColor: tourArea.colour}}>
            { tourArea.display_name }
        </span>
    </>;
};

module.exports = {
    TourRosterViewer,
};