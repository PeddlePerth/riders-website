function timespan_intersects(ts1, ts2) {
    const [begin1, len1] = ts1, [begin2, len2] = ts2; // expand

    // check if there is an overlap
    if ((begin1 >= begin2 && begin1 <= begin2 + len2) || (begin1 + len1 >= begin2 && begin1 + len1 <= begin2 + len2) ||
        (begin2 >= begin1 && begin2 <= begin1 + len1) || (begin2 + len2 >= begin1 && begin2 + len2 <= begin1 + len1)) {
        // return true only if overlap is not solely on boundary
        return (begin1 + len1 != begin2) && (begin1 != begin2 + len2);
    }
    return false;
}

function timespan_difference(ts1, ts2) {
    const x0 = ts1[0], x1 = ts1[0] + ts1[1];
    const y0 = ts2[0], y1 = ts2[0] + ts2[1];
    return [[x0, y0 - x0], [y1, x1 - y1]];
}

class TimespanLock {
    constructor(first_time, last_time) {
        this.start = first_time;
        this.duration = last_time - first_time; // total width of available timespan in ms
        this.lock_times = []; // maintain a list of time intervals in strictly ascending order by begin time (first to last)
    }

    lock_timespan(start, end) {
        if (this.is_locked_during(start, end)) return false; // do not allow overlaps
        var insertAt = this.lock_times.findIndex(([begin, len]) => start >= begin);
        if (insertAt < 0) insertAt = 0;
        this.lock_times.splice(insertAt, 0, [start, end - start]);
        return true;
    }

    unlock_timespan(start, end) {
        const new_lock_times = [];
        for (var i = 0; i < this.lock_times.length; i++) {
            var ts = this.lock_times[i];
            const unlock_len = end - start;
            const unlock_ts = [start, unlock_len];
            if (timespan_intersects(unlock_ts, ts)) {
                let diff = timespan_difference(ts, unlock_ts);
                // difference parts may be zero or negative, exclude these
                // timespan is wiped out, remove it from the list (replace with difference)
                diff.filter((diff) => diff[1] > 0).forEach((diff) => new_lock_times.push(diff));
            } else {
                new_lock_times.push(ts);
            }
        }
        this.lock_times = new_lock_times;
    }

    is_locked_during(start, end) {
        if (end === undefined) end = start;

        // assume locked outside of time range
        if (start > this.start + this.duration || end < this.start) return true;

        // contradiction!
        if (end < start) return false;

        for (var timespan of this.lock_times) {
            if (timespan_intersects([start, end - start], timespan))
                return true;
        }
        return false;
    }

    // test if available for ANY times during specified interval
    is_available_during(start, end) {
        if (end === undefined) end = start; // for specific time point
        if (start > this.start + this.duration || end < this.start) return false; // not available outside time range
        if (end < start) return false; // not available during negative time
        for (var timespan of this.lock_times) {
            if (!timespan_intersects([start, end - start], timespan))
                return true;
        }
        return false;
    }

    get_timespans() {
        // return timespans in [start, end] format
        let prev = [null, this.start], timespans = [];
        for (var ts of this.lock_times) {
            if (ts[0] <= prev[1]) {
                prev[1] = ts[0];
                continue;
            }
            timespans.push(prev);
            prev = [ts[0], ts[0] + ts[1]];
        }
        if (this.start + this.duration <= prev[1]) {
            prev[1] = null;
        }
        timespans.push(prev);

        return timespans;
    }

    toString() {
        return this.lock_times.map(ts => ((new Date(ts[0])).toLocaleTimeString() + ' for ' + ts[1]/(1000*60) + ' mins')).join(', ');
    }
}

TimespanLock.timespan_intersects = timespan_intersects;
TimespanLock.timespan_difference = timespan_difference;

module.exports = TimespanLock;
