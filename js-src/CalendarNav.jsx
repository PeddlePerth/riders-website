const { useMemo } = require('react');
const { Col, Row, Stack } = require('react-bootstrap');
const { firstDayOfWeek, firstDayOfMonth, addMonths, addDays, WEEKDAYS, MONTHS, datesEqual, format_iso_date } = require('./utils');

function getDateRange(date, monthsBehind, monthsAhead) {
    var first = new Date(date);
    firstDayOfMonth(first);
    addMonths(first, -monthsBehind);
    firstDayOfWeek(first);

    var last = new Date(date);
    firstDayOfMonth(last);
    addMonths(last, monthsAhead + 1);
    if (last.getDate() !== 1) {
        firstDayOfWeek(last);
        addDays(last, 7);
    }
    return [first, last];
}

// call with useMemo()
// constructs array of 3 months, with each element an array representing each week of those months
// each week consists of an array of Dates for each day
function getCalendarDays(date, monthsBehind, monthsAhead) {
    var start = new Date(date); // start of month (use the start of the month before our current date)
    firstDayOfMonth(start);
    addMonths(start, -monthsBehind);

    // begin from the first day of previous month, add one day at a time, and store the Date and day of week for each month
    // months is an array of arrays of { date: Date(), dow: 0-6, inMonth: bool }
    const months = [];
    months.first_date = new Date(start);
    var d = new Date(start), dow = 0;
    firstDayOfWeek(d);
    var curMonth = start.getMonth();
    const endMonth = (curMonth + monthsBehind + 1 + monthsAhead) % 12; // note: months are zero-indexed
    var curMonthWeeks = [], curWeek = []; // array of days for current week
    //console.log('calendar starting from', start, ' and first day', d);

    while (curMonth !== endMonth) {
        // construct a full 7-day week
        curWeek.push({
            date: new Date(d), // copy rather than reference
            isodate: format_iso_date(d),
            dow: dow,
            inMonth: curMonth === d.getMonth(),
        });

        if (dow === 0) {
            curWeek.begin = d.valueOf();
        }

        let prev = new Date(d);
        addDays(d, 1); // increment day
        dow = (dow + 1) % 7;

        // check for end of week
        if (dow !== 0) { 
            continue;
        } else {
            curWeek.end = prev.valueOf();
            curWeek.month = curMonth;
            curMonthWeeks.push(curWeek);
            curWeek = [];
        }

        // check if we rolled over to the next month yet, at the end of the week
        let m = d.getMonth();
        let nextMonth = (curMonth + 1) % 12;
        if (m === nextMonth) {
            // finalize current month
            curMonthWeeks.title = MONTHS[curMonth];
            curMonthWeeks.month = curMonth;

            months.push(curMonthWeeks);

            // next month: go back to the start of the previous week
            if (d.getDate() !== 1) {
                d = prev;
                firstDayOfWeek(d);
            }
            //console.log("end of curMonth="+curMonth+" nextMonth="+nextMonth+" first day = ", d);
            
            curMonth = nextMonth;
            curMonthWeeks = []; // reset array for next month
        }
    }

    addDays(d, -1);
    months.last_date = d;

    return months;
}

function CalendarDay({ date, inMonth=true, today=false, active=false, onSelect, badges=[] }) {
    const cls = "CalendarDay" + (today ? " today" : "") + (active ? " active" : "") + 
        (inMonth ? " inMonth" : "") + (onSelect ? " interactive" : "");
    return <Col
        className={cls} 
        onClick={(e) => (inMonth && onSelect) ? onSelect(date) : null}>
            <span className="date">{date.getDate()}</span>&nbsp;
            <div className="Badges">{ badges }&nbsp;</div>
        </Col>;
}

function CalendarWeekHeader() {
    return <Row className="CalendarWeek CalendarWeekHeader g-0">{
        WEEKDAYS.map((day, index) => <Col className="p-1" key={index}>{ day }</Col>)
    }</Row>;
}

function CalendarWeek({ children, weekStart, active=false, onSelect }) {
    const cls = "CalendarWeek g-0" + (active ? " active" : "") + (onSelect ? " interactive" : "");
    return <Row className={cls}
            onClick={(e) => onSelect ? onSelect(weekStart) : null}>
            { children }
        </Row>;
}

function CalendarMonth({ children, title, active=false }) {
    const cls = "CalendarMonth" + (active ? " active" : "");
    return <Col className={cls}>
        <div>
        <h4>{ title }</h4>
        <CalendarWeekHeader/>
        { children }
        </div>
        </Col>;
}

// date is currently selected "today's date"
function CalendarNav({ selectedDay=null, selectedWeek=null, today=(new Date()), badges={}, onSelectWeek, onSelectDay, monthsAhead, monthsBehind }) {
    date = new Date(today);
    date.setHours(0, 0, 0, 0);
    var firstOfMonth = new Date(today);
    firstDayOfMonth(firstOfMonth);
    firstOfMonth = firstOfMonth.getTime();

    const months = useMemo(
        () => getCalendarDays(firstOfMonth, monthsBehind, monthsAhead),
        [firstOfMonth, monthsBehind, monthsAhead]);
    
    return <Row className="CalendarNav g-0" xs="1" sm="3">
        {
            months.map((month, mi) => <CalendarMonth 
                key={ mi }
                title={ month.title }
                active={ date.getMonth() === month.month }
                children={
                month.map((week, wi) => (<CalendarWeek
                    key={ wi }
                    active={ (selectedDay !== null && 
                        selectedDay.getMonth() === week.month && 
                        selectedDay >= week.begin && 
                        selectedDay <= week.end) || 
                        (selectedWeek !== null && selectedWeek.getTime() == week.begin)
                    }
                    onSelect={onSelectWeek}
                    weekStart={ week.begin }
                    children={
                    week.map((day) => 
                        <CalendarDay 
                            key={ day.dow }
                            date={ day.date }
                            inMonth={day.inMonth}
                            onSelect={onSelectDay}
                            today={ datesEqual(day.date, today) }
                            active={ selectedDay && day.inMonth && datesEqual(day.date, selectedDay) }
                            badges={ day.inMonth ? badges[day.isodate] : [] }
                        />)
                }/>))
            }/>)
        }
    </Row>;
}



module.exports = { CalendarNav, getDateRange };