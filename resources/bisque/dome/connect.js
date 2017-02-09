/* Java Script */
sky6RASCOMTheSky.Connect();
if (sky6RASCOMTheSky.IsConnected == 0) {
    Out = "Not connected"
} else {
    sky6RASCOMTheSky.ConnectDome();
    sky6RASCOMTheSky.CoupleDome();
    Out = "Dome coupled";
};
