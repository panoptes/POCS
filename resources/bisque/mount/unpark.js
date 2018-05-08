var Out;
sky6RASCOMTele.Connect();
if (sky6RASCOMTele.IsConnected == 0) {
    Out = "Not connected";
} else {
    sky6RASCOMTele.Abort();
    sky6RASCOMTele.Asynchronous = $async;
    sky6RASCOMTele.Unpark();

    Out = JSON.stringify({
    	"error": sky6RASCOMTele.LastSlewError,
    	"success": true,
    });
};
