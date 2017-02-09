/* Java Script */
var Out;
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
