/* Java Script */
Out = '';

sky6RASCOMTele.Abort();
sky6RASCOMTele.Jog($arcmin, "$direction");

while (!sky6RASCOMTele.IsSlewComplete) {
    sky6Web.Sleep(1000);
}
Out = JSON.stringify({
	"msg": "Mount jogged",
    "success": true,
});    
