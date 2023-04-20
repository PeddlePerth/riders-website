const TimespanLock = require('./TimespanLock.js');

const date = new Date(1648261006860); //Sat Mar 26 2022 10:16:46 GMT+0800 (Australian Western Standard Time)

function time(t) {
    return Date.parse('2022-01-20 ' + t);
}

const tl = new TimespanLock(time('10:00'), time('17:00'));

function intersects(a, b, val) {
    let dotest = (a, b) =>
        test(`intersection of ${a} and ${b}`, () => {
            expect(TimespanLock.timespan_intersects(a, b)).toBe(val);
        });
    dotest(a, b);
    dotest(b, a);
}

function diff(a, b, expected) {
    test(`difference: ${a} - ${b}`, () => {
        expect(JSON.stringify(TimespanLock.timespan_difference(a, b))).toBe(JSON.stringify(expected));
    });
}

describe('timespan intersect works', () => {
    intersects([0, 9], [10, 10], false);
    intersects([21, 10], [10, 10], false);
    intersects([11, 8], [10, 10], true);
    intersects([15, 0], [10, 10], true);
    intersects([10, 10], [10, 10], true);
    intersects([10, 0], [10, 10], false);
    intersects([20, 10], [10, 10], false);
    intersects([0, 10], [10, 10], false);
    intersects([20, 10], [10, 10], false);
    intersects([10, 9], [10, 10], true);
    intersects([15, 5], [10, 10], true);
});

describe('timespan difference works', () => {
    diff([0, 10], [5, 5], [[0, 5], [10, 0]]);
    diff([5, 5], [0, 10], [[5, -5], [10, 0]]);
    diff([0, 10], [2, 6], [[0, 2], [8, 2]]);
});

test('timespan lock works', () => {

    expect(tl.toString()).toBe('');
    // test the initial boundaries
    expect(tl.is_locked_during(time('10:00'), time('17:00'))).toBe(false);
    expect(tl.is_locked_during(time('11:00'), time('17:00'))).toBe(false);
    expect(tl.is_locked_during(time('10:00'), time('16:00'))).toBe(false);

    // lock a time and test the lock time boundaries
    expect(tl.lock_timespan(time('10:30'), time('12:30'))).toBe(true);
    function testlock1 () {
        expect(tl.is_locked_during(time('10:30'), time('12:30'))).toBe(true);
        expect(tl.is_locked_during(time('10:31'), time('12:30'))).toBe(true);
        expect(tl.is_locked_during(time('10:31'), time('12:29'))).toBe(true);
        expect(tl.is_locked_during(time('12:00'), time('12:01'))).toBe(true);
        expect(tl.is_locked_during(time('12:00'), time('12:00'))).toBe(true);
        expect(tl.is_locked_during(time('10:30'), time('10:30'))).toBe(false);
        expect(tl.is_locked_during(time('10:20'), time('10:30'))).toBe(false);
        expect(tl.is_locked_during(time('10:00'), time('10:29'))).toBe(false);
        expect(tl.is_locked_during(time('12:29'), time('12:30'))).toBe(true);
        expect(tl.is_locked_during(time('12:29'), time('12:31'))).toBe(true);
        expect(tl.is_locked_during(time('12:30'), time('12:31'))).toBe(false);
        expect(tl.is_locked_during(time('12:30'), time('17:00'))).toBe(false);
        expect(tl.is_locked_during(time('10:00'), time('10:30'))).toBe(false);
    }
    testlock1();

    // lock another timespan
    expect(tl.lock_timespan(time('12:30'), time('13:00'))).toBe(true);
    function testlock2() {
        expect(tl.is_locked_during(time('10:30'), time('13:00'))).toBe(true);
        expect(tl.is_locked_during(time('10:00'), time('17:00'))).toBe(true);
        expect(tl.is_locked_during(time('10:30'), time('10:30'))).toBe(false);
        expect(tl.is_locked_during(time('12:30'), time('12:30'))).toBe(false);
        expect(tl.is_locked_during(time('12:30'), time('13:00'))).toBe(true);
        expect(tl.is_locked_during(time('13:00'), time('13:01'))).toBe(false);
        expect(tl.is_locked_during(time('12:00'), time('12:59'))).toBe(true);
        expect(tl.is_locked_during(time('13:00'), time('17:00'))).toBe(false);
    }
    testlock2();

    tl.unlock_timespan(time('10:30'), time('12:00'));
    expect(tl.is_locked_during(time('10:00'), time('10:30'))).toBe(false);
    expect(tl.is_locked_during(time('10:30'), time('12:00'))).toBe(false);
    expect(tl.is_locked_during(time('12:00'), time('12:30'))).toBe(true);
    expect(tl.is_locked_during(time('12:00'), time('13:30'))).toBe(true);
    expect(tl.is_locked_during(time('12:00'), time('13:00'))).toBe(true);
    expect(tl.is_locked_during(time('13:00'), time('14:00'))).toBe(false);

    tl.unlock_timespan(time('12:00'), time('13:00'));
    expect(tl.is_locked_during(time('13:00'), time('14:00'))).toBe(false);
    expect(tl.is_locked_during(time('12:00'), time('12:30'))).toBe(false);
    expect(tl.is_locked_during(time('12:00'), time('13:30'))).toBe(false);
    expect(tl.is_locked_during(time('12:00'), time('13:00'))).toBe(false);
    expect(tl.is_locked_during(time('10:00'), time('17:00'))).toBe(false);
    expect(tl.is_locked_during(time('11:00'), time('17:00'))).toBe(false);
    expect(tl.is_locked_during(time('10:00'), time('16:00'))).toBe(false);

});

afterAll(() => console.log(tl));