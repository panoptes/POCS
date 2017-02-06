/* Java Script */
var Out="";
var dRA = 0.0;
var dDec = 0.0;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected==0) {
   Out = "Not connected";
} else {
    sky6Utils.ConvertStringToRA("$ra");
    dRA = sky6Utils.dOut0;
    Out = dRA;
    sky6Utils.ConvertStringToDec("$dec");
    dDec = sky6Utils.dOut0;
    Out += " " + dDec;
    sky6RASCOMTele.Asynchronous = $async;
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.SlewToRaDec(dRA,dDec,'radec_coords');
    while(!sky6RASCOMTele.IsSlewComplete) {
        sky6Web.Sleep(1000);
    }
    Out = "Slew to RA/Dec complete.";
}