/* Java Script */
sky6RASCOMTele.Abort();
sky6RASCOMTele.SetTracking(0, 0, $ra_rate, $dec_rate);
Out = JSON.stringify({
	"msg": 'Sidereal rate set',
	"success": true,
});