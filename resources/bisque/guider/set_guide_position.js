/* Java Script */
var msg, success;
ccdsoftCamera.Autoguider = 1;
ccdsoftCamera.Asynchronous = false;
if (ccdsoftCamera.Connect()) {
    msg = "DFError: Not connected";
    success = false;
} else {
    ccdsoftCamera.BinX = $bin;
    ccdsoftCamera.BinY = $bin;
    ccdsoftCamera.GuideStarX = $x;
    ccdsoftCamera.GuideStarY = $y;
    ccdsoftCamera.MoveToX = $x;
    ccdsoftCamera.MoveToY = $y;
    msg = "Guiding at x=$x y=$y.";
    success = true;
}
Out = JSON.stringify({
  "success": success,
  "msg": msg,
});
