sky6Dome.Connect();
if (sky6Dome.IsConnected == 0) {
    Out = "Not connected"
} else {
    Out = sky6Dome.Park();
};
