/* Java Script */
var Out;
sky6RASCOMTele.ConnectAndDoNotUnpark();
if (Application.initialized) {
    Out = JSON.stringify({
    	"success": sky6RASCOMTele.IsConnected > 0,
    	"msg": "Mount connected",
    });
} else {
    Out = JSON.stringify({
    	"msg": 'TheSkyX not initialized',
    	"success": false,
    });
}
