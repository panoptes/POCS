/* Java Script */
Out = '';
sky6RASCOMTele.GetRaDec();
var dRa = sky6RASCOMTele.dRa;
var dDec = sky6RASCOMTele.dDec;

sky6Utils.ComputeHourAngle(dRa);
var dHA = sky6Utils.dOut0;

sky6Utils.ConvertEquatorialToString(dRa, dDec, 5);
var coordsString1 = sky6Utils.strOut;

sky6RASCOMTele.GetAzAlt();

Out = JSON.stringify({
    "ra": dRa,
    "dec": dDec,
    "alt": parseFloat(Math.round(sky6RASCOMTele.dAlt * 100) / 100).toFixed(2),
    "az": parseFloat(Math.round(sky6RASCOMTele.dAz * 100) / 100).toFixed(2),
    "ha": parseFloat(Math.round(dHA * 10000) / 10000).toFixed(4),
    "success": true,
});
