/* Java Script */
if (sky6RASCOMTheSky.IsConnected == 0) {
    Out = "Not connected"
} else {
    sky6RASCOMTheSky.Disconnect();
    sky6RASCOMTheSky.Quit();
    Out = "Quitting";
};

