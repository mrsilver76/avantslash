#!/usr/bin/perl

print("Content-Type: text/plain\n\n");
$ok = 1;
$cgi_ok = 1;
$beg_admin = "Or ask your server administrator/web hosting provider to install this.\n\n"; 

print("Testing CGI.pm availability.\n");
eval "use CGI;";
if ($@) {
    print("Perl CGI module is not available; try\n".
	  "(Debian/Ubuntu) apt-get install libhttp-server-simple-perl\n".
	  "(Redhat/CentOS) yum install perl-cgi\n".
	  $beg_admin);
    $ok = 0;
    $cgi_ok = 0;
} else {
    print("OK.\n\n");
}

print("Testing LWP.pm availability.\n");
eval "use LWP;";
if ($@) {
    print("Perl LWP module is not available; try\n".
	  "(Debian/Ubuntu) apt-get install libwww-perl\n".
	  "(Redhat/CentOS) yum install perl-libwww-perl\n".
	  $beg_admin);
    $ok = 0;
} else {
    print("OK.\n\n");
}

if ($cgi_ok) {
    print("Testing URI.pm availability.\n");
    eval "use URI;";
    if ($@) {
	print("Perl URI module is not available; try\n".
	      "(Debian/Ubuntu) apt-get install liburi-perl\n".
	      "(Redhat/CentOS) yum install perl-URI\n".
	      $beg_admin);
	$ok = 0;
    } else {
	print("OK.\n\n");
    }
}


eval "use Cwd;";
if ($@) {
    print("Perl Cwd module not available; something is is seriously messed up.\n");
    $ok = 0;
}

print("Testing write permissions on cache directory.\n");
if (! -d "cache") {
    $cwd = getcwd();
    print("No cache directory available.\n".
	  "Expected cache directory here: $cwd/cache .\n\n");
    $ok = 0;
} else {
    $result = open($fh, ">cache/_test_");
    if (!$result) {
	print("Cannot write to cache directory: $!\n".
	    "Try this: chmod 777 cache\n\n");
	$ok = 0;
    } else {
	unlink("cache/_test_");
	print("OK.\n\n");
    }
}

print("Checking CGI file permissions.\n");
@statdata = stat("avantify.cgi");
if ($#statdata == -1) {
    $cwd = getcwd();
    print("File not available: $cwd/avantify.cgi .");
    $ok = 0;
} else {
    $mode = $statdata[2] & 07777;
    if (($mode & 0111) != 0111 || ($mode & 0022) != 0) {
	printf("avantify.cgi has suspicious permissions %04o.\n".
	       "Try: chmod 755 avantify.cgi\n\n", $mode);
	$ok = 0;
    } else {
	print("OK.\n\n");
    }
}



if ($ok) {
    print("Everything seems to be OK!\n");
}



