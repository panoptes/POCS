var Out = "";
sky6RASCOMTheSky.Connect();
if (sky6RASCOMTheSky.IsConnected == 0) {
    Out = "Not connected";
} else {
    // Center screen on target
    sky6RASCOMTheSky.SetTelescopeParkPosition();

    Out = JSON.stringify({
        "msg": sky6Web.LASTCOMERROR,
        "error": sky6Web.LASTCOMERROR,
        "success": true,
    });
}