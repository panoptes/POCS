/* Java Script */
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Connect();
Out = JSON.stringify({
	"success": true,
	"msg": "Guider connected",
});
