/* Java Script */
var Out;
if (Application.initialized) {
    sky6RASCOMTele.Connect();
    if (sky6RASCOMTele.IsConnected == 0) {
        Out = "Not connected";
    } else {
        Out = sky6RASCOMTele.IsConnected;
    };
} else {
    Out = 'TheSkyX not initialized';
}
