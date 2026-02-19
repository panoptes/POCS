/* Java Script */
var msg, success;
if (ccdsoftCamera.Connect()) {
   msg = "DFError: Not connected";
   success = false;
} else {
   ccdsoftCamera.AutoSaveOn = false;
   ccdsoftCamera.AutoguiderExposureTime = 1;
   ccdsoftCamera.AutoguiderDelayAfterCorrection = 1;
   ccdsoftCamera.Delay = 1;
   ccdsoftCamera.Asynchronous = true;
   ccdsoftCamera.TrackBoxX = 35;
   ccdsoftCamera.TrackBoxY = 35;
   ccdsoftCamera.Autoguide(); 
   msg = "Guiding started";
   success = true;
}
Out = JSON.stringify({
        "success": success,
        "msg": msg,
});

