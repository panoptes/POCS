/* Java Script */
var Out;
var Err;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected";
} else {
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.FindHome();
    while (!sky6RASCOMTele.IsSlewComplete) {
        sky6Web.Sleep(1000);
    }
    Out = "Mount homed. LastSlewError: " + sky6RASCOMTele.LastSlewError;
};
