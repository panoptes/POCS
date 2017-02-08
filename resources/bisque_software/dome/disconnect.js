/* Java Script */
if (sky6RASCOMTheSky.IsConnected == 0) {
    Out = "Not connected"
} else {
    sky6RASCOMTheSky.DisconnectDome();
    Out = "Dome disconnected";
};
