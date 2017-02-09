/* Java Script */
var Out;
sky6RASCOMTele.ConnectAndDoNotUnpark();
if (Application.initialized) {
    Out = JSON.stringify({
    	"success": sky6RASCOMTele.IsConnected,
    });
} else {
    Out = JSON.stringify({
    	"error": 'TheSkyX not initialized',
    	"success": false,
    });
}
