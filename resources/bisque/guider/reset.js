/* Java Script */
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = false;
ccdsoftCamera.Disconnect();
ccdsoftCamera.Connect();
Out = JSON.stringify({
	"success": true,
	"msg": "Guider reset",
});