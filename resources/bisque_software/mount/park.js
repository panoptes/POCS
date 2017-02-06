/* Java Script */
var Out;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected";
} else {
    sky6RASCOMTele.Asynchronous = $async;
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.Park();
    while (!sky6RASCOMTele.IsSlewComplete) {
        sky6Web.Sleep(1000);
    }
    Out = "Mount parked. LastSlewError: " + sky6RASCOMTele.LastSlewError;
};
