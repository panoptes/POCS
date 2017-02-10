/* Java Script */
sky6RASCOMTele.Abort();
sky6RASCOMTele.SetTracking(1, 1, 0, 0);
Out = JSON.stringify({
	"msg": 'Tracking started',
	"success": true,
});