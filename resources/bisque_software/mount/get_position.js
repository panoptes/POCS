/* Java Script */
var Out;
var dRA;
var dDec;
var dAz;
var dAlt;
var coordsString1;
var coordsString2;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected"
} else {
    sky6RASCOMTele.GetRaDec();
    dRA = sky6RASCOMTele.dRa;
    dDec = sky6RASCOMTele.dDec;
    sky6Utils.ComputeHourAngle(dRA);
    dHA = sky6Utils.dOut0;
    sky6Utils.ConvertEquatorialToString(dRA, dDec, 5);
    coordsString1 = sky6Utils.strOut;
    sky6RASCOMTele.GetAzAlt();
    Out = coordsString1;
    Out += " Alt: " + parseFloat(Math.round(sky6RASCOMTele.dAlt * 100) / 100).toFixed(2);
    Out += " Az: " + parseFloat(Math.round(sky6RASCOMTele.dAz * 100) / 100).toFixed(2);
    Out += " HA: " + parseFloat(Math.round(dHA * 10000) / 10000).toFixed(4);
};
