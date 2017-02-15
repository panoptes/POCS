/* Java Script */
var Out;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = 0;
ccdsoftCamera.Connect();
Out = JSON.stringify({
	"success": true,
	"msg": "Guider connected",
});
