/* Java Script */
sky6Utils.ConvertStringToRA("$ra");
var ra = sky6Utils.dOut0;

sky6Utils.ConvertStringToDec("$dec");
var dec = sky6Utils.dOut0;

sky6RASCOMTele.Asynchronous = false;
sky6RASCOMTele.Abort();
RunJavaScriptOutput.writeLine("Start [async=" + sky6RASCOMTele.Asynchronous + "]");
RunJavaScriptOutput.writeLine("Before slew call");
RunJavaScriptOutput.writeLine("Slew complete: " + sky6RASCOMTele.IsSlewComplete);
sky6RASCOMTele.SlewToRaDec(ra, dec, '');
RunJavaScriptOutput.writeLine("After slew call");
RunJavaScriptOutput.writeLine("Slew Complete: " + sky6RASCOMTele.IsSlewComplete);
RunJavaScriptOutput.writeLine("Going to loop");
while (!sky6RASCOMTele.IsSlewComplete) {
	RunJavaScriptOutput.writeLine("Slew Complete: " + sky6RASCOMTele.IsSlewComplete);
    sky6Web.Sleep(1000);
}
RunJavaScriptOutput.writeLine("Out of loop");
	RunJavaScriptOutput.writeLine("Slew Complete: " + sky6RASCOMTele.IsSlewComplete);
Out = JSON.stringify({
    "ra": ra,
    "dec": dec,
    "success": sky6RASCOMTele.IsSlewComplete,
    "msg": "Slew complete"
});    
