/* Java Script */
var Out;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected";
} else {
    sky6RASCOMTele.Asynchronous = $async;
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.Unpark();
    while (!sky6RASCOMTele.IsSlewComplete) {
        sky6Web.Sleep(1000);
    }

    Out = JSON.stringify({
    	"error": sky6RASCOMTele.LastSlewError,
        "msg": "Mount unparked",
    	"success": sky6RASCOMTele.IsParked() == false,
    });
};
