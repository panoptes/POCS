sky6RASCOMTele.Abort();
sky6RASCOMTele.Asynchronous = $async;
sky6RASCOMTele.FindHome();

Out = JSON.stringify({
	"msg": 'Mount homed',
	"success": true,
    "error": sky6RASCOMTele.LastSlewError	
});