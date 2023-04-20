const { useState } = require("react");
const { format_num, pad_zeros } = require("./utils");

// 12 hour time input with two sliders
const TimeInput = ({ value, onChange }) => {
    const hours = value.getHours();
    const pm = hours >= 12;
    const hours12 = pad_zeros(hours > 12 ? hours - 12 : hours, 2);
    const mins = pad_zeros(value.getMinutes(), 2);

    return <span className="TimeInput d-flex">
        <input key={1}
            type="number"
            value={hours12}
            onChange={(e) => {
                let val = new Date(value);
                let hh = parseInt(e.target.value);
                if (hh == 0 && pm) {
                    val.setHours(12);
                } else if (hh == 13 && pm) {
                    val.setHours(13);
                } else if (pm && hh < 12) {
                    val.setHours(hh + 12);
                } else if (!pm && hh >= 0) {
                    val.setHours(hh);
                } else {
                    return;
                }
                onChange(val);
            }} />
        <span className="fw-bold fs-5">:</span>
        <input key={2} type="number" value={mins}
            onChange={(e) => {
                let val = new Date(value);
                let mm = parseInt(e.target.value)
                if (mm < 0 && hours > 0) {
                    val.setHours(hours - 1);
                    val.setMinutes(59);
                } else if (mm >= 60 && hours < 23) {
                    val.setHours(hours + 1);
                    val.setMinutes(0);
                } else if (mm >= 0 && mm < 60) {
                    val.setMinutes(mm);
                } else {
                    return;
                }
                onChange(val);
            }}
        />
        <span className="fw-bold">{pm ? 'pm' : 'am' }</span>
    </span>;
}

module.exports = {TimeInput};