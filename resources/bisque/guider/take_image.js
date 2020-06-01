/* Java Script */
var msg, success;
var keep = ccdsoftCamera.AutoSaveOn;
var im;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.BinX = $bin;
ccdsoftCamera.BinY = $bin;
ccdsoftCamera.AutoguiderExposureTime = $exptime;
ccdsoftCamera.Asynchronous = false;
if (ccdsoftCamera.Connect()) {
   msg = "DFError: Not connected";
   success = false;
} else {
    ccdsoftCamera.Abort();
    while (ccdsoftCamera.State != 0) {
      sky6Web.Sleep(1000);
    }
    ccdsoftCamera.AutoSaveOn = false;
    ccdsoftCamera.ImageReduction = 0;
    ccdsoftCamera.TakeImage();
    while (ccdsoftCamera.State != 0) {
      sky6Web.Sleep(1000);
    }
    im = ccdsoftAutoguiderImage;
    im.AttachToActiveAutoguider();
    im.Path = "$path";
    im.setFITSKeyword("GUIDER","success");
    im.Save();
    ccdsoftCamera.AutoSaveOn = keep;
    msg = "Test image stored in $path";
    success = true;
}

Out = JSON.stringify({
    "success": success,
    "msg": msg,
});