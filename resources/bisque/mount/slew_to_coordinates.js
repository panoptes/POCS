/* Java Script */
Out = '';
sky6Utils.ConvertStringToRA("$ra");
var ra = sky6Utils.dOut0;

sky6Utils.ConvertStringToDec("$dec");
var dec = sky6Utils.dOut0;

sky6RASCOMTele.Asynchronous = $async;
sky6RASCOMTele.Abort();
sky6RASCOMTele.SlewToRaDec(ra, dec, 'radec_coords');

while (!sky6RASCOMTele.IsSlewComplete) {
    sky6Web.Sleep(1000);
}
Out = JSON.stringify({
    "ra": ra,
    "dec": dec,
    "slewing": sky6RASCOMTele.IsSlewComplete,
    "success": true,
});    
