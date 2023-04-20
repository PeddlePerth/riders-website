function getRandString() {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_+";
    str = "";
    for (var i = 0; i < 64; i++) {
        str += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return str;
}

$(function () {
    $('.token-widget').each(function () {
        var input = $('input[type=hidden]', this);
        var label = $('code', this);
        $('input.token-clear', this).on('click', function () {
            input.val(null);
            label.text("None");
        });
        $('input.token-set', this).on('click', function () {
            var val = getRandString();
            input.val(val);
            label.text(val);
        });
    });
});