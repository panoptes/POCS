/* Java Script */
var side;
sky6RASCOMTele.Abort();
sky6RASCOMTele.DoCommand(11, "dummy");
side = sky6RASCOMTele.DoCommandOutput;

var pier;
if (side == 0) {
    pier = "west";
} else {
    pier = "east";
}

Out = JSON.stringify({
    "success": true,
    "side": pier,
});
