import { Badge } from "react-bootstrap";
import "./peddleweb.css"; // this is so webpack picks up the css
import { RiderTourSchedule } from "./RiderTourSchedule";
import TourDashboard from "./TourDashboard";
import { TourScheduleViewer } from "./TourScheduleViewer";
import { VenuesReport } from "./VenuesReport";

const $ = require('jquery');
const ReactDOM = require('react-dom');
const { createElement } = require('react');
const TourScheduleEditor = require('./TourScheduleEditor.js');
const AjaxDataComponent = require('./AjaxDataComponent.js');
const TourPayReport = require('./TourPayReport.js');
const { parse_datetime, post_data } = require('./utils');

function load_schedule_editor() {
    const container = document.getElementById("schedule-content");
    const extraPostData = {
        tours_date: window.jsvars.tours_date,
        tour_area_id: window.jsvars.tour_area_id,
    };

    ReactDOM.render(
        <AjaxDataComponent
            ref={ el => window.scheduleEditor = el }
            dataConsumer={TourScheduleEditor}
            extraPostData={extraPostData}
            postUrl={window.jsvars.urls.tour_sched_data}
            dataRef={ (data) => window.tourData = data }
            getPostData={ ({ tours, sessions }) => ({
                tours, sessions
            })}
        />,
        container
    );
}

function load_tour_pay_report() {
    const container = document.getElementById("report-content");
    const extraPostData = {
        report_start_date: window.jsvars.start_date,
        report_end_date: window.jsvars.end_date,
    };

    ReactDOM.render(
        createElement(AjaxDataComponent, {
            ref: el => window.tourReports = el,
            dataConsumer: TourPayReport,
            extraPostData: extraPostData,
            postUrl: window.jsvars.urls.tour_report_data,
            dataRef: (data) => window.tourData = data,
            getPostData: function (data) {
                const payslots = [].concat(
                    ...Object.values(data.riders).map(
                        rider => [].concat(...Object.values(rider.pay_days))
                    ));
                return {
                    payslots: payslots,
                    tour_pay_config: data.tour_pay_config,
                };
            },
        }),
        container);
}

function load_venues_report() {
    post_data(window.jsvars.urls.venues_report_data, {
        start_date: window.jsvars.start_date,
        end_date: window.jsvars.end_date,
    }, function (ok, data) {
        ReactDOM.render(
            ok ?
            createElement(VenuesReport, {
                startDate: parse_datetime(window.jsvars.start_date),
                endDate: parse_datetime(window.jsvars.end_date),
                venues: data.venues,
            }) :
            createElement('h3', {}, 'Error loading data: ' + data),
            document.getElementById('report-content')
        )
    });

}

function load_tour_dashboard(selected) {
    ReactDOM.render(
        createElement(TourDashboard, {
            date_today: parse_datetime(window.jsvars.date),
            data_url: window.jsvars.data_url,
            last_scan: window.jsvars.last_scan,
            scan_interval: window.jsvars.scan_interval,
            scan_ok: window.jsvars.last_scan_begin >= ((new Date()).valueOf() - window.jsvars.scan_interval * 60 * 1000) ||
                window.jsvars.last_scan >= ((new Date()).valueOf() - window.jsvars.scan_interval * 60 * 1000 * 2),
            selected: selected,
            onSelect: (date) => {
                //console.log("selected date", date);
                load_tour_dashboard(date);
            },
        }),
        document.getElementById('dashboard')
    );
}

function load_tour_schedules() {
    const container = document.getElementById('schedule-content');

    ReactDOM.render(<TourScheduleViewer
        initialAreaId={window.jsvars.tour_area_id}
        tourAreas={window.jsvars.tour_areas}
        initialDate={window.jsvars.tours_date}
        isAdmin={window.jsvars.is_admin}
        myRiderId={window.jsvars.rider_id}
        />,
        container);
}

function load_rider_schedule() {
    const container = document.getElementById('schedule-content');
    ReactDOM.render(<RiderTourSchedule 
        initialDate={window.jsvars.date}
        />,
        container);
}

// this is the entry point to the javascript stuff, keep everything here
$(function () {
    //console.log("We are on the page:", window.page_name);

    switch(window.page_name) {
        case 'schedules_editor':
            load_schedule_editor();
            break;
        case 'report_tours':
            load_tour_pay_report();
            break;
        case 'report_venues':
            load_venues_report();
            break;
        case 'tour_dashboard':
            load_tour_dashboard();
            break;
        case 'schedules':
            load_tour_schedules();
            break;
        case 'schedules_rider':
            load_rider_schedule();
            break;
    }
});