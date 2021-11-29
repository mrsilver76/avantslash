#!/usr/bin/perl

$href = "http://$ENV{HTTP_HOST}$ENV{SCRIPT_NAME}";
$href =~ s/index.cgi$/avantify.cgi/;

print("Content-type: text/html\n".
      "Status: 301 Moved\n".
      "Location: $href\n\n");
print("<html><body><href='$href'>Moved here</a></body></html>\n");

    
