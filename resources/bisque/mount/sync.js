/* Java Script */

/*
* Sync telescope
*/
var im = ccdsoftCameraImage;
var tmpfile = "/var/tmp/tmp.fits";
ImageLink.scale = 2.85;
ccdsoftCamera.CameraExposureTime = 5;
// Take the image
ccdsoftCamera.Autoguider = true;
ccdsoftCamera.Asynchronous = false;
if (ccdsoftCamera.Connect()) {
    Out = "Not connected";
    return;
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
    im.Path = tmpfile;
    im.Save();
    ccdsoftCamera.AutoSaveOn = true;
}
// ImageLink the image and sync the telescope to it
ImageLink.pathToFITS = tmpfile;
ImageLink.unknownScale = 0;
try {
    ImageLink.execute();
} catch (e) {
    im.New(10, 10, 16);
    im.Visible = 0;
    im.DetatchOnClose = 1;
    im.Path = "/var/tmp/mount_sync_output.fits";
    im.setFITSKeyword("RESULT", "failed");
    im.Save();
    im.Close();
}
im.New(10, 10, 16);
im.Visible = 0;
im.DetatchOnClose = 1;
im.Path = "/var/tmp/mount_sync_output.fits";
if (ImageLinkResults.succeeded) {
    im.setFITSKeyword("RESULT", "success");
    im.setFITSKeyword("RA_PS", ImageLinkResults.imageCenterRAJ2000);
    im.setFITSKeyword("DEC_PS", ImageLinkResults.imageCenterDecJ2000);
    im.setFITSKeyword("SCALE_PS", ImageLinkResults.imageScale);
    im.setFITSKeyword("ISMIR_PS", ImageLinkResults.imageIsMirrored);
    sky6RASCOMTele.Connect();
    sky6RASCOMTele.Sync(ImageLinkResults.imageCenterRAJ2000, ImageLinkResults.imageCenterDecJ2000, "plate_solve");
    Out = "Telescope synced to image";
} else {
    im.setFITSKeyword("RESULT", "failure");
    Out = "ImageLink failed. Telescope is not synced.";
}
im.Save();
im.Close();
