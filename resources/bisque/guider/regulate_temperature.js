/* Java Script */
var msg, success;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Connect();
ccdsoftCamera.TemperatureSetPoint = -5;
ccdsoftCamera.RegulateTemperature = 1;
ccdsoftCamera.ShutDownTemperatureRegulationOnDisconnect = 0;
msg = "Camera connected";

Out = JSON.stringify({
	"success": success,
	"msg": msg,
});