const $ = require('jquery');
const { createElement } = require('react');

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

function post_data(url, data, callback) {
    return $.ajax(url, {
        data: JSON.stringify(data),
        method: 'POST',
        dataType: "json",
        contentType: "application/json",
        headers: {
            "X-CSRFToken": csrftoken,
        },
        success: (data, textStatus, jqXHR) => callback(true, data),
        error: (jqXHR, textStatus, errorThrown) => callback(false, errorThrown),
    });
}

function plural(n, str1, str2) {
    if (n == 0) return n + str2;
    if (n == 1) return n + str1;
    return n + str2;
}

function pad_zeros(num, len) {
    // from https://stackoverflow.com/questions/2998784/how-to-output-numbers-with-leading-zeros-in-javascript
    return String(num).padStart(len, '0');
}

function format_num(num, leading_zeros, decimals, max_decimals) {
    if (num === Infinity || isNaN(num) || num === null || num === undefined) {
        return '';
    }

    if (decimals === undefined) decimals = 0;
    if (max_decimals === undefined) max_decimals = 10;

    const decimal = (num % 1);
    const fixed_decimal = decimal.toFixed(max_decimals).slice(2);
    const full_decimal = fixed_decimal.replace(/0*$/, '');
    const i = pad_zeros(Math.floor(num), leading_zeros);
    if (decimals > 0 || (max_decimals > 0 && full_decimal.length > 0)) {
        //console.log(num, i, full_decimal, fixed_decimal, decimals, max_decimals);
        if (full_decimal.length < decimals) {
            return i + "." + fixed_decimal.slice(0, decimals);
        } else if (full_decimal.length > 0 && full_decimal.length <= max_decimals && full_decimal.length >= decimals && max_decimals > 0) {
            return i + "." + full_decimal;
        } else {
            return i + "." + fixed_decimal;
        }
    } else {
        return i;
    }
}

function parse_datetime(timestamp) {
    if (typeof(timestamp) == "number") timestamp = new Date(timestamp);
    else if (typeof(timestamp) == "string") timestamp = new Date(parseInt(timestamp));
    return new Date(timestamp);
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WEEKDAYS_LONG = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];

function get_weekday(date, long=false) {
    let day = (parse_datetime(date).getDay() + 6) % 7;
    return long ? WEEKDAYS_LONG[day] : WEEKDAYS[day];
}

function format_date(timestamp) {
    if (!timestamp) return "N/A";

    let date = parse_datetime(timestamp);
    return pad_zeros(date.getDate(), 2) + "/" + pad_zeros(date.getMonth() + 1, 2) + "/" + pad_zeros(date.getYear() % 100, 2);
}

// Get a short date, eg. "Mon 10/09"
function format_short_date(timestamp) {
    if (!timestamp) return "N/A";
    timestamp = parse_datetime(timestamp);
    return get_weekday(timestamp) + " " + pad_zeros(timestamp.getDate(), 2) + "/" + pad_zeros(timestamp.getMonth() + 1, 2);
}

function format_iso_date(timestamp) {
    if (!timestamp) return "0000-00-00";
    ts = parse_datetime(timestamp);
    return `${pad_zeros(ts.getFullYear(), 4)}-${pad_zeros(ts.getMonth() + 1, 2)}-${pad_zeros(ts.getDate(), 2)}`;
}

function format_time(timestamp) {
    if (timestamp) {
        timestamp = parse_datetime(timestamp);
        return `${pad_zeros(timestamp.getHours(), 2)}:${pad_zeros(timestamp.getMinutes(), 2)}`;
    } else {
        return "N/A";
    }
}

function format_time_12h(timestamp) {
    if (timestamp) {
        const dt = parse_datetime(timestamp);
        const hours = dt.getHours();
        return `${hours > 12 ? hours - 12 : hours}:${pad_zeros(dt.getMinutes(), 2)}${hours >= 12 ? 'pm' : 'am'}`;
    } else {
        return "N/A";
    }
}

function format_datetime(timestamp) {
    if (!timestamp) return "N/A";
    timestamp = parse_datetime(timestamp);
    return `${format_time_12h(timestamp)} ${format_date(timestamp)}`;
}

function format_datetime_short(timestamp) {
    if (!timestamp) return "N/A";
    timestamp = parse_datetime(timestamp);
    return `${format_time(timestamp)} ${pad_zeros(timestamp.getDate(), 2)}/${pad_zeros(timestamp.getMonth() + 1, 2)}`;
}

function format_timedelta(delta) {
    delta = Math.floor(delta / 1000);
    const sec = delta % 60;
    delta = Math.floor(delta / 60);
    const mins = delta % 60;
    delta = Math.floor(delta / 60);
    const hours = delta % 24;
    delta = Math.floor(delta / 24);
    const days = delta;

    if (days) return hours ? `${days}d ${hours}h` : `${days}d`;
    if (hours) return mins ? `${hours}h ${mins}m` : `${hours}h`
    if (mins) return sec ? `${mins}m ${sec}s` : `${mins}m`;
    else return `${sec}s`;
}

function parse_time(time_str, date) {
    const datetime = new Date(date.toTimestamp());
    const [hh, mm] = time_str.split(":");
    datetime.setHours(parseInt(hh));
    datetime.setMinutes(parseInt(mm));
    return datetime;
}

// from https://stackoverflow.com/questions/931207/is-there-a-jquery-autogrow-plugin-for-text-fields
function autoGrowInput(el, opts) {
    o = $.extend({
        maxWidth: 1000,
        minWidth: 20,
        comfortZone: 10,
    }, opts);

    const elm = $(el);

    var minWidth = o.minWidth || elm.width(),
        val = '',
        input = elm,
        testSubject = $('<tester/>').css({
            position: 'absolute',
            top: -9999,
            left: -9999,
            width: 'auto',
            fontSize: input.css('fontSize'),
            fontFamily: input.css('fontFamily'),
            fontWeight: input.css('fontWeight'),
            letterSpacing: input.css('letterSpacing'),
            whiteSpace: 'nowrap'
        });

    function checkSize() {
        if (val === (val = input.val())) {return;}

        // Enter new content into testSubject
        var escaped = val.replace(/&/g, '&amp;').replace(/\s/g,'&nbsp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        testSubject.html(escaped);

        // Calculate new width + whether to change
        var testerWidth = testSubject.width(),
            newWidth = (testerWidth + o.comfortZone) >= minWidth ? testerWidth + o.comfortZone : minWidth,
            currentWidth = input.width(),
            isValidWidthChange = (newWidth < currentWidth && newWidth >= minWidth)
                                    || (newWidth > minWidth && newWidth < o.maxWidth);

        // Animate width
        if (isValidWidthChange) {
            input.width(newWidth);
        }
    };

    testSubject.insertAfter(input);

    elm.on('keyup keydown blur update', checkSize);
    checkSize();

    return function unbind() {
        elm.off('keyup keydown blur update', checkSize);
        testSubject.remove();
    }
}

function autoHeightTd(el) {
    const jel = $(el);
    const tdHeight = jel.closest('td').height();
    if (tdHeight) jel.height(tdHeight);
}

// from https://stackoverflow.com/questions/1865563/set-cursor-at-a-length-of-14-onfocus-of-a-textbox/1867393#1867393
function setCursor(node, pos) {
    node = (typeof node == "string" || node instanceof String) ? document.getElementById(node) : node;

    if (!node) {
        return false;
    } else if (node.createTextRange) {
        var textRange = node.createTextRange();
        textRange.collapse(true);
        textRange.moveEnd(pos);
        textRange.moveStart(pos);
        textRange.select();
        return true;
    } else if (node.setSelectionRange) {
        node.setSelectionRange(pos,pos);
        return true;
    }

    return false;
}

function firstDayOfMonth(date) {
    date.setHours(0, 0, 0, 0);
    date.setDate(1);
}

// using Monday as the first day of week (JS prefers Sunday)
function firstDayOfWeek(date) {
    date.setHours(0, 0, 0, 0);
    var dayOffs = (date.getDay() + 6) % 7;
    addDays(date, -dayOffs);
}

function addMonths(date, months) {
    var years = Math.floor(Math.abs(months) / 12.0) * (months / Math.abs(months));
    months = months % 12;
    date.setFullYear(date.getFullYear() + years);
    date.setMonth(date.getMonth() + months);
}

function addDays(date, days) {
    date.setTime(date.getTime() + (days * 86400 * 1000));
}

function datesEqual(a, b) {
    const aa = new Date(a), bb = new Date(b);
    aa.setHours(0, 0, 0, 0);
    bb.setHours(0, 0, 0, 0);
    return aa.getTime() === bb.getTime();
}

function getMailto(email, subject, body) {
    var uri = "mailto:" + (email ? encodeURI(email) : '');
    if (!(subject || body)) return uri;

    uri += "?subject=" + encodeURI(subject);
    uri += "&body=" + encodeURI(body);
    return uri;
}

// from https://stackoverflow.com/questions/45831191/generate-and-download-file-from-js
function downloadFile(filename, contents, filetype='text/plain;charset=utf-8') {
    var a = document.createElement('a');
    a.download = filename;
    a.href = window.URL.createObjectURL(new Blob([contents], {type: filetype}));
    a.click();
}

function formatCSV(rows) {
    return rows.map(row =>
        row.map(field => (field ? ('"' + field.replace('"', '""') + '"') : '')).join(',')
    ).join('\r\n');
}

function htmlLines(text, replacements) {
    var textLines;
    if (typeof(text) == 'string') {
        if (replacements) {
            for (var r of replacements) {
                text = text.replaceAll(r, '');
            }
        }
        textLines = text.trim().split('\n');
    } else if (text && text.constructor === Array) {
        textLines = text;
    }
    let lines = [];
    textLines.forEach((line, index) => {
        lines.push(line);
        if (index < text.length - 1) lines.push(<br key={index}/>)
    })
    return lines;
}

function getWeekName(today, weekStart) {
    let thisWeek = new Date(today);
    firstDayOfWeek(thisWeek);
    let weeksAhead = Math.round((weekStart.valueOf() - thisWeek.valueOf()) / (7 * 24 * 60 * 60 * 1000));
    if (weeksAhead < -1) {
        return `${-weeksAhead} weeks ago`;
    } else if (weeksAhead == -1) {
        return 'Last week';
    } else if (weeksAhead == 0) {
        return 'This week';
    } else if (weeksAhead == 1) {
        return 'Next week';
    } else {
        return `${weeksAhead} weeks from now`;
    }
}

function today() {
    let now = new Date();
    now.setMilliseconds(0);
    now.setSeconds(0);
    now.setMinutes(0);
    now.setHours(0);
    return now;
}

module.exports = {
    getCookie,
    pad_zeros,
    format_num,
    get_weekday,
    format_date,
    format_datetime,
    format_datetime_short,
    format_short_date,
    format_iso_date,
    format_time,
    format_time_12h,
    format_timedelta,
    parse_time,
    parse_datetime,
    post_data,
    autoGrowInput,
    autoHeightTd,
    setCursor,
    firstDayOfMonth,
    firstDayOfWeek,
    addMonths,
    addDays,
    datesEqual,
    WEEKDAYS,
    MONTHS,
    plural,
    getMailto,
    downloadFile,
    formatCSV,
    htmlLines,
    getWeekName,
    today,
};