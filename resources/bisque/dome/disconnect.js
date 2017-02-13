/* Java Script */
sky6RASCOMTheSky.DisconnectDome();
Out = JSON.stringify({
	"success": sky6Dome.IsConnected == 0,
	"msg": "Dome disconnected",
});    