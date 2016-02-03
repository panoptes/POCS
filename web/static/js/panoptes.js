function add_chat_item(name, msg, time){

    item = '<li class="left"><img class="avatar" alt="Dennis Ji" src="/static/img/pan.png">';
    item = item + '<span class="message"><span class="arrow"></span>';
    item = item + '<span class="from label label-success">' + name + '</span> &nbsp;';
    item = item + '<span class="time">' + time + '</span>';
    item = item + '<span class="text">' + msg + '</span>';
    item = item + '</span></li>';

    $('#bot_chat').prepend(item);
}

// Find all the elements with the class that matches a return value
// and update their html
function update_info(status){
    $.each(status, function(key, val){
        $('.' + key).each(function(idx, elem){
            $(elem).html(val);
        })
    });
}

var messageContainer = document.getElementById('ws_status');
function WebSocketTest(server) {
    if ("WebSocket" in window) {
        var ws = new WebSocket("ws://" + server + "/ws/");
        ws.onopen = function() {
            // messageContainer.innerHTML = "Connection open...";
            ws.send("Connection established");
        };
        ws.onmessage = function (evt) {
            var type = evt.data.split(' ', 1)[0];
            console.log(type);
            var received_msg = evt.data.substring(evt.data.indexOf(' ') + 1)

            console.log(received_msg);

            var msg = jQuery.parseJSON(received_msg);

            if (type == 'PAN001'){
                add_chat_item(type, msg.message, msg.timestamp);
            }
            if (type == 'STATUS'){
                update_info(msg['observatory']);
                $('.current_state').html(msg['state']);
                refresh_images();
            }

        };
        ws.onclose = function() {
            messageContainer.innerHTML = "Connection is closed...";
        };
    } else {
        messageContainer.innerHTML = "WebSocket NOT supported by your Browser!";
    }
}

// Refresh all images with `img_refresh` container class
function refresh_images(){
    console.log("Refreshing images")
    $.each($('.img_refresh img'), function(idx, img){
        reload_img(img);
    });
}

// Reload individual image
function reload_img(img){
    base = $(img).attr('src').split('?')[0];

    // Hack for others
    if(base.startsWith('http')){
        new_src = $(img).attr('src');
    } else {
        new_src = base + '?' + Math.random()
    }


    $(img).attr('src', new_src);
}

// Startup
$( document ).ready(function() {
    // Image refresh timer
    second = 1000;

    WebSocketTest(window.location.host);

    // Refresh images
    // setInterval(refresh_images, 15 * second);
})
