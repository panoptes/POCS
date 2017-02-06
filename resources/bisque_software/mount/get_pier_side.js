/* Java Script */
var side;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected"
} else {
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.DoCommand(11, "dummy");
    side = sky6RASCOMTele.DoCommandOutput;
    if (side == 0) {
        Out = "OTASide: West ";
    } else {
        Out = "OTASide: East ";
    }
};
