/* Java Script */

/*
* Dither
* Params:
*   arcmin:
*   direction:
*   async:
*/
var Out="";
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected==0) {
   Out = "Not connected";
} else {
    sky6RASCOMTele.Asynchronous = $async;
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.Jog($arcmin,$direction);
    while(!sky6RASCOMTele.IsSlewComplete) {
        sky6Web.Sleep(1000);
    }
    Out = "Dither complete.";
}