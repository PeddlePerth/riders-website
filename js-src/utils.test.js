/* Unit test code - should not be published to website (but meh, whatever, if it is for some reason) */
const { format_time_12h, format_num } = require('./utils.js');

const date = new Date(1648261006860); //Sat Mar 26 2022 10:16:46 GMT+0800 (Australian Western Standard Time)

test('format 12h time', () => {
    expect(format_time_12h(date)).toBe('10:16am');
});

test('format numbers', () => {
    // test leading zeros
    expect(format_num(10, 0, 0)).toBe('10');
    expect(format_num(10, 1, 0)).toBe('10');
    expect(format_num(10, 2, 0)).toBe('10');
    expect(format_num(10, 3, 0)).toBe('010');
    expect(format_num(10, 5, 0)).toBe('00010');

    // test decimal places
    expect(format_num(2/3, 0, 0, 0)).toBe('0');
    expect(format_num(2/3, 0, 0, 1)).toBe('0.7');
    expect(format_num(2/3, 0, 0, 2)).toBe('0.67');
    expect(format_num(2/3, 0, 0, 5)).toBe('0.66667');
    expect(format_num(2/3, 1, 0, 5)).toBe('0.66667');
    expect(format_num(2/3, 2, 0, 5)).toBe('00.66667');
    expect(format_num(1 + 2/3, 2, 0, 5)).toBe('01.66667');
    expect(format_num(1 + 2/3, 0, 0, 5)).toBe('1.66667');

    // test min-max decimals
    expect(format_num(2/3, 1, 0, 5)).toBe('0.66667');
    expect(format_num(2/3, 1, 5, 5)).toBe('0.66667');
    expect(format_num(2/3, 1, 2, 5)).toBe('0.66667');
    expect(format_num(1.23456, 0, 2, 3)).toBe('1.235');
    expect(format_num(1.2, 0, 2, 3)).toBe('1.20');
    expect(format_num(1.23456, 0, 2, 8)).toBe('1.23456');

    expect(format_num(12345.678, 0, 2, 2)).toBe('12345.68');
    expect(format_num(12345.6, 0, 2, 2)).toBe('12345.60');
    expect(format_num(12345, 0, 2, 2)).toBe('12345.00');
    expect(format_num(12345.009, 0, 2, 2)).toBe('12345.01');

    expect(format_num(2/3, 1, 0, 6)).toBe('0.666667');

    expect(format_num(null, 0, 0)).toBe('');
    expect(format_num(NaN, 0, 0)).toBe('');
    expect(format_num(Infinity, 0, 0)).toBe('');
    expect(format_num(undefined, 0, 0)).toBe('');
});