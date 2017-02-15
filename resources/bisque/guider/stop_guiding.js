/* Java Script */
var Out;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = 0;
ccdsoftCamera.Abort();
Out = JSON.stringify({
	"success": true,
	"msg": "Guiding stopped",
});
