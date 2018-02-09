var msg, success;
if (ccdsoftCamera.Connect()) {
   msg = "DFError: Not connected";
   success = false;
} else {
   ccdsoftCamera.Asynchronous = $async;
   ccdsoftCamera.AutoSaveOn = false;
   ccdsoftCamera.AutoguiderExposureTime = $exptime;
   ccdsoftCamera.AutoguiderDelayAfterCorrection = 1;
   ccdsoftCamera.Delay = 1;
   ccdsoftCamera.BinX = $bin;
   ccdsoftCamera.BinY = $bin;
   ccdsoftCamera.TrackBoxX = 35;
   ccdsoftCamera.TrackBoxY = 35;
   ccdsoftCamera.Autoguide(); 
   msg = "Guiding started";
   success = true;
}
Out = JSON.stringify({
	"success": success,
   "status": ccdsoftCamera.Status,
	"msg": msg
});
