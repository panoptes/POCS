Out = '';

sky6RASCOMTele.Abort();
sky6RASCOMTele.Asynchronous = $async;
sky6RASCOMTele.Jog($arcmin, "$direction");

Out = JSON.stringify({
	"msg": "Mount moved $arcmin to $direction",
    "success": true,
	"error": sky6RASCOMTele.LastSlewError    
});    
