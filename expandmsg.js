<--THIS IS A SCRIPT TEMPLATE FOR EMBEDDING IN HTML CODE-->
var sid=<SID>, threshold=<THRESHOLD>;
function load_comment(cid) {
    var elx = document.getElementById("x"+cid);
    var req=new XMLHttpRequest();
    if (!req) { elx.innerHTML = "Not supported"; return false; }
    elx.innerHTML = "Loading...";

    req.onreadystatechange = function() {
	if (req.readyState == 4) {
	    if (req.responseText.length > 50)
		document.getElementById("cmt"+cid).innerHTML = req.responseText;
	    else
		elx.innerHTML = "[Retry expand]";
	}
    }
    req.open("GET", "<SELF_URL>?ajax="+cid+","+sid+"&threshold="+threshold, true);
    req.send("");
    return false;
}
