/* Java Script */
var Out;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = 0;
ccdsoftCamera.Disonnect();
Out = JSON.stringify({
	"success": true,
	"msg": "Guider disconnected",
});
