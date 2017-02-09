/* Java Script */
var Out;
sky6RASCOMTheSky.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected";
} else {
    // julianDay = $jd;
    // dstOption = $dst;
    // systemClock = $systemClock;
    // location = "$location";
    // lon = $lon;
    // lat = $lat;
    // timeZone = $tz;
    // elevation = $elevation;
    // sky6RASCOMTheSky.SetWhenWhere(julianDay, dstOption, systemClock, location, lon, lat, timeZone, elevation);
    Out = sky6RASCOMTheSky.GetWhenWhere();
};
