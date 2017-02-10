/* Java Script */
var horizon = 30;
var Out = "";
sky6RASCOMTheSky.Connect();
if (sky6RASCOMTheSky.IsConnected == 0) {
    Out = "Not connected";
} else {
    sky6Utils.ConvertStringToRA("$ra");
    var ra = sky6Utils.dOut0;

    sky6Utils.ConvertStringToDec("$dec");
    var dec = sky6Utils.dOut0;

    // Check if above horizon
    sky6Utils.ConvertRADecToAzAlt(ra, dec);
    var az = sky6Utils.dOut0;
    var alt = sky6Utils.dOut1;

    if (alt > horizon){ // HARD-CODED VALUE
        sky6StarChart.EquatorialToStarChartXY(ra, dec);

        // Display target
        var x_pos = sky6StarChart.dOut0;
        var y_pos = sky6StarChart.dOut1;

        sky6StarChart.ClickFind(x_pos, y_pos);

        // Center screen on target
        sky6RASCOMTheSky.dScreenRa = ra;
        sky6RASCOMTheSky.dScreenDec = dec;

        sky6StarChart.Refresh();

        Out = JSON.stringify({
            "ra": ra,
            "dec": dec,
            "theskyx_x": x_pos,
            "theskyx_y": y_pos,
            "success": true,
            "msg": "Target coordinates set",
        });
    } else {
        Out = JSON.stringify({
            "msg": "Target: " + alt.toFixed(2) + " deg / Horizon: " + horizon + " deg",
            "success": false,
        });        
    }
}
