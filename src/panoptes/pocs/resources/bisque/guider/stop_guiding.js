/* Java Script */
var msg, success;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = true;
if (ccdsoftCamera.Connect()) {
   msg = "DFError: Not connected";
   success = false;
} else {
    ccdsoftCamera.Abort();
    state = ccdsoftCamera.State;
    while (ccdsoftCamera.State != 0) {
      sky6Web.Sleep(1000);
    }
    msg = "Guiding stopped.";
    success = true;
}

Out = JSON.stringify({
	"success": success,
	"msg": "Guiding stopped",
});
