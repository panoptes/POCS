/* Java Script */
sky6Utils.ConvertStringToRA("$ra");
var ra = sky6Utils.dOut0;

sky6Utils.ConvertStringToDec("$dec");
var dec = sky6Utils.dOut0;

sky6RASCOMTele.Asynchronous = false;
sky6RASCOMTele.Abort();
sky6RASCOMTele.SlewToRaDec(ra, dec, '');

while (!sky6RASCOMTele.IsSlewComplete) {
    sky6Web.Sleep(1000);
}
Out = JSON.stringify({
    "ra": ra,
    "dec": dec,
    "success": sky6RASCOMTele.IsSlewComplete,
    "msg": "Slew complete"
});    
