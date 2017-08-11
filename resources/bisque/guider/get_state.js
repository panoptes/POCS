/* Java Script */
var msg, success;
if (ccdsoftCamera.Connect()) {
    msg = "DFError: Not connected";
    success = false;
} else {
    var state = ccdsoftCamera.State;
    switch (state) {
        case 0:
            msg = 'Idle';
            break;
        case 1:
            msg = 'Exposing';
            break;
        case 2:
            msg = 'Exposing Series';
            break;
        case 3:
            msg = 'Focus';
            break;
        case 4:
            msg = 'Moving';
            break;
        case 5:
            msg = 'Autoguiding';
            break;
        case 6:
            msg = 'Calibrating';
            break;
        case 7:
            msg = 'Exposing Color';
            break;
        case 8:
            msg = 'Autofocus';
            break;
        case 9:
            msg = 'Autofocus';
            break;
    }
    success = true;
}

Out = JSON.stringify({
    "success": success,
    "msg": msg,
});
