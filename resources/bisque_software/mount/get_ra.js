/* Java Script */
var Out="";
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected==0) {
   Out = "Not connected";
} else {
	sky6RASCOMTele.GetRaDec();
    Out = sky6RASCOMTele.dRa;
}