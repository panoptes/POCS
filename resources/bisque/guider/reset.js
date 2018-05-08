ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = $async;
ccdsoftCamera.Disconnect();
ccdsoftCamera.Connect();

Out = JSON.stringify({
	"success": true,
    "status": ccdsoftCamera.Status,	
	"msg": "Guider reset"
});