/* Java Script */
Out = '';
sky6Utils.ConvertStringToRA("$ra");
var ra = sky6Utils.dOut0;

sky6Utils.ConvertStringToDec("$dec");
var dec = sky6Utils.dOut0;

sky6RASCOMTele.Asynchronous = $async;
sky6RASCOMTele.Abort();
sky6RASCOMTele.SlewToRaDec(ra, dec, 'radec_coords');

Out = JSON.stringify({
    "ra": ra,
    "dec": dec,
    "success": true
});    
