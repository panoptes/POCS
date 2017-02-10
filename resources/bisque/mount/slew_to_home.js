/* Java Script */
sky6RASCOMTele.Abort();
sky6RASCOMTele.FindHome();
while (!sky6RASCOMTele.IsSlewComplete) {
    sky6Web.Sleep(1000);
}

Out = JSON.stringify({
	"msg": 'Mount homed',
	"success": true,
});