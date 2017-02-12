/* Java Script */
sky6Dome.OpenSlit();
while (sky6Dome.IsOpenComplete == 0) {
    sky6Web.Sleep(1000);
}
Out = JSON.stringify({
	"success": true,
	"msg": "Slit Opened",
});    