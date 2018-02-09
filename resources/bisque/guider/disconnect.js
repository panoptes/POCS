ccdsoftCamera.Autoguider = 1;
Out = JSON.stringify({
	"success": ccdsoftCamera.Disconnect() == 0, 
   	"status": ccdsoftCamera.Status,		
	"msg": "Guider disconnected",
});
