/* Java Script */
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected"
} else {
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.DoCommand(0, "dummy");
    sky6RASCOMTele.DoCommand(1, "dummy");
    sky6RASCOMTele.DoCommand(2, "dummy");
    sky6RASCOMTele.DoCommand(6, "dummy");
    Out = "Serial port purged";
};
