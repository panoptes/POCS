/* Java Script */
sky6Dome.CloseSlit();
while (sky6Dome.IsCloseComplete == 0) {
    sky6Web.Sleep(1000);
}
Out = JSON.stringify({
	"success": true,
	"msg": "Slit Closed",
});    