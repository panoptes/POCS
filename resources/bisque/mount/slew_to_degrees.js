/* Java Script */
var dRA = $ra;
var dDec = $dec;
sky6RASCOMTele.Asynchronous = false;
sky6RASCOMTele.Abort();
sky6RASCOMTele.SlewToRaDec(dRA, dDec, '');
while (!sky6RASCOMTele.IsSlewComplete) {
    sky6Web.Sleep(1000);
}

var msg = "Slew to RA/Dec complete.";

Out = JSON.stringify({
    "ra": ra,
    "dec": dec,
    "success": sky6RASCOMTele.IsSlewComplete,
    "msg": msg,
});    
