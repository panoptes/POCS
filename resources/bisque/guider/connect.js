ccdsoftCamera.Autoguider = 1;
Out = JSON.stringify({
	"success": !ccdsoftCamera.Connect() == 0,
   	"status": ccdsoftCamera.Status,
	"msg": "Guider connected",
});
