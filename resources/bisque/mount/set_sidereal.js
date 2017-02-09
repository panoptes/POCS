/* Java Script */
var Out;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected";
} else {
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.SetTracking(1, 1, 0, 0);
    Out = "Mount tracking at sidereal rate. LastSlewError: " + sky6RASCOMTele.LastSlewError;
};
