/* Java Script */
sky6RASCOMTheSky.Connect();
if (sky6RASCOMTheSky.IsConnected == 0) {
    Out = JSON.stringify({
    	"success": false,
    	"msg": "Not connected",
    });        
} else {
    sky6RASCOMTheSky.ConnectDome();
    sky6RASCOMTheSky.CoupleDome();
    Out = JSON.stringify({
    	"success": sky6Dome.IsConnected > 0,
    	"msg": "Dome coupled",
    });    
};
