/* Java Script */
sky6RASCOMTheSky.DisconnectDome();
Out = JSON.stringify({
	"success": sky6RASCOMTele.IsConnected > 0,
	"msg": "Dome disconnected",
});    