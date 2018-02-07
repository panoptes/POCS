/* Java Script */
Out = '';
sky6RASCOMTele.Asynchronous = $async;
sky6RASCOMTele.Abort();
sky6RASCOMTele.ParkAndDoNotDisconnect();
while (!sky6RASCOMTele.IsSlewComplete) {
    sky6Web.Sleep(1000);
}

Out = JSON.stringify({
    "success": sky6RASCOMTele.IsParked()
});
