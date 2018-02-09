sky6RASCOMTele.Abort();
sky6RASCOMTele.Asynchronous = $async;
sky6RASCOMTele.ParkAndDoNotDisconnect();

Out = JSON.stringify({
	"error": sky6RASCOMTele.LastSlewError,	
    "success": true
});
