/* Java Script */
var Out="";
sky6RASCOMTheSky.Connect();
if (sky6RASCOMTheSky.IsConnected==0) {
   Out = "Not connected";
} else {
    sky6Utils.ConvertStringToDec("$dec");
    sky6RASCOMTheSky.dScreenDec = sky6Utils.dOut0;
    sky6StarChart.Refresh();	
    Out = sky6RASCOMTheSky.dScreenDec;
}