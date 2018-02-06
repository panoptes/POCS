/* Java Script */
sky6RASCOMTele.Asynchronous = $async;
Out = '';
sky6RASCOMTele.GetRaDec();
var dRa = sky6RASCOMTele.dRa;
var dDec = sky6RASCOMTele.dDec;

sky6Utils.ComputeHourAngle(dRa);
var dHA = sky6Utils.dOut0;

sky6Utils.ConvertEquatorialToString(dRa, dDec, 5);
var coordsString1 = sky6Utils.strOut;

sky6RASCOMTele.GetAzAlt();

var is_tracking = false;
if (sky6RASCOMTele.IsTracking == 1 || SelectedHardware.mountModel == 'Telescope Mount Simulator'){
	is_tracking = true;
}

Out = JSON.stringify({
    "ra_rate": sky6RASCOMTele.dRaTrackingRate,
    "dec_rate": sky6RASCOMTele.dDecTrackingRate,
    "tracking": is_tracking,
    "slewing": sky6RASCOMTele.IsSlewComplete == 0,
    "connected": sky6RASCOMTele.IsConnected == 1,
    "error": sky6RASCOMTele.LastSlewError,
    "parked": sky6RASCOMTele.IsParked()
});